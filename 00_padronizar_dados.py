# -*- coding: utf-8 -*-
"""
00_padronizar_dados.py
======================
Padroniza e consolida os arquivos IFData do Banco Central do Brasil
(2000 a 2024, trimestral).

FONTES / FORMATOS ENCONTRADOS EM `dados_bcb_olinda/`:
  * Formato SNAKE  (2000-2013): colunas em minúsculo com "_" e decimal com vírgula
      -> tipo_instituicao;cod_inst;ano_mes;nome_relatorio;...;saldo
  * Formato PASCAL (2014-2024): colunas em PascalCase e decimal com ponto
      -> TipoInstituicao;CodInst;AnoMes;NomeRelatorio;...;Saldo
  * Formato RANKING (1994-1999): semestral, "ranking;instituicao;...".
      FORA DO ESCOPO (o orientando optou por 2000 em diante, trimestral).

O QUE ESTE SCRIPT FAZ MELHOR QUE A VERSÃO ANTERIOR (Gemini/GNN):
  1. Detecta o formato automaticamente por arquivo (não assume só um padrão);
  2. Normaliza os NOMES DAS COLUNAS dos dois formatos para um schema único;
  3. Converte `saldo` de texto BR (vírgula) ou internacional (ponto) de forma
     segura, validando a taxa de erros de conversão por arquivo;
  4. Padroniza `cod_inst` com zero à esquerda (8 dígitos) e valida presença;
  5. CORRIGE O BUG DE DUPLA CONTAGEM: o pivot do código anterior (Gemini)
     somava 'Ativo Total', 'Patrimônio Líquido', 'Captações', etc. que existem
     no Resumo E no relatório detalhado, DOBRANDO os valores (verificado: o
     Ativo Total do 00058338/201403 saiu 2x maior em gnn_nodes_features.csv).
     Aqui cada coluna larga leva o prefixo do relatório e o nome completo;
  6. Gera um RELATÓRIO DE QUALIDADE em texto (para conferência na dissertação).

SAÍDAS (pasta `dados/`):
  * ifdata_longo_padronizado.csv.gz  -> formato longo (1 linha por conta/inst./período)
  * ifdata_wide_panel.csv            -> matriz larga  (1 linha por inst./período)
  * relatorio_padronizacao.txt       -> relatório de qualidade da padronização
"""

from __future__ import annotations

import glob
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------- #
# 0. Configurações
# ----------------------------------------------------------------------------- #
RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA_ORIGEM = os.path.join(RAIZ, "dados_bcb_olinda")
PASTA_SAIDA = os.path.join(RAIZ, "dados")
ARQUIVO_LONGO = os.path.join(PASTA_SAIDA, "ifdata_longo_padronizado.csv.gz")
ARQUIVO_WIDE = os.path.join(PASTA_SAIDA, "ifdata_wide_panel.csv")
ARQUIVO_RELATORIO = os.path.join(PASTA_SAIDA, "relatorio_padronizacao.txt")

# Mapa de normalização das duas versões de cabeçalho (snake_case + PascalCase)
RENOMEIA_COLUNA = {
    "tipo_instituicao": "tipo_instituicao",
    "tipoinstituicao": "tipo_instituicao",
    "cod_inst": "cod_inst",
    "codinst": "cod_inst",
    "ano_mes": "ano_mes",
    "anomes": "ano_mes",
    "nome_relatorio": "nome_relatorio",
    "nomerelatorio": "nome_relatorio",
    "numero_relatorio": "numero_relatorio",
    "numerorelatorio": "numero_relatorio",
    "grupo": "grupo",
    "conta": "conta",
    "nome_coluna": "nome_coluna",
    "nomecoluna": "nome_coluna",
    "descricao_coluna": "descricao_coluna",
    "descricaocoluna": "descricao_coluna",
    "saldo": "saldo",
}
COLUNAS_ORIGINAIS = [
    "tipo_instituicao",
    "cod_inst",
    "ano_mes",
    "nome_relatorio",
    "numero_relatorio",
    "grupo",
    "conta",
    "nome_coluna",
    "descricao_coluna",
    "saldo",
]
COLUNAS_FINAIS = [
    "tipo_instituicao",
    "cod_inst",
    "ano_mes",
    "nome_relatorio",
    "numero_relatorio",
    "grupo",
    "conta",
    "nome_coluna_completa",
    "nome_coluna",
    "descricao_coluna",
    "saldo",
]
# ----------------------------------------------------------------------------- #
# 1. Funções auxiliares
# ----------------------------------------------------------------------------- #
def detectar_formato(caminho: str) -> str:
    """Detecta o formato do arquivo a partir da primeira linha (cabeçalho)."""
    with open(caminho, encoding="utf-8-sig", errors="replace") as fh:
        hdr = fh.readline().strip()
    if hdr.startswith('"tipo_') or hdr.startswith("tipo_"):
        return "snake"
    if hdr.startswith("Tipo"):
        return "pascal"
    return "outro"  # ex.: ranking (1994-1999) ou arquivos ilegíveis


def limpar_nome_coluna(df: pd.DataFrame, col: str = "nome_coluna") -> pd.Series:
    """Limpa o NOME COMPLETO da conta (1ª + 2ª linha), trocando quebra por ' - '.

    Ex.: 'Credores por Antecipação de Valor Residual (j)' é o nome completo
    (as duas linhas originais viram uma só). Isso PRESERVA a distinção entre
    contas com o mesmo nome resumido (ex.: '(e3)' vs '(j)').

    O nome RESUMIDO (só a 1ª linha) é derivado depois, em `ler_arquivo_normalizado`.
    """
    serie = df[col].astype(str)
    serie = serie.str.replace("\r", "", regex=False)
    serie = serie.str.replace("\n", " - ", regex=False)
    serie = serie.str.strip().str.replace('"', "", regex=False)
    serie = serie.str.replace(r"\s{2,}", " ", regex=True)
    return serie


def nome_resumido(serie: pd.Series) -> pd.Series:
    """Fica só com a primeira linha do nome (ex.: 'Ativo Total')."""
    return serie.str.split(" - ", regex=False).str[0].str.strip()


def converter_saldo_br(serie: pd.Series) -> pd.Series:
    """Converte 'saldo' de texto para float, aceitando vírgula OU ponto decimal.

    - Formato antigo BR:  '778846,1'  / '123.456,78' (milhar com ponto)
    - Formato novo:       '585686400.36'
    Regra: se a string tem vírgula, assume vírgula decimal (BR clássico) e
    remove todos os pontos de milhar; caso contrário converte direto.
    """
    s = serie.astype(str).str.strip().str.replace('"', "", regex=False)
    tem_virgula = s.str.contains(",").fillna(False)
    s.loc[tem_virgula] = (
        s.loc[tem_virgula].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    )
    out = pd.to_numeric(s, errors="coerce")
    return out


def ler_arquivo_normalizado(caminho: str) -> pd.DataFrame | None:
    """Lê um arquivo IFData e devolve DF padronizado (longo), ou None."""
    formato = detectar_formato(caminho)
    if formato == "outro":
        return None  # legacy 1994-1999 (semestral) ou arquivo inútil

    df = pd.read_csv(caminho, sep=";", dtype=str, low_memory=False, encoding="utf-8-sig")
    df.columns = [RENOMEIA_COLUNA.get(c.strip().lower(), c.strip().lower()) for c in df.columns]

    colunas_faltando = [c for c in COLUNAS_ORIGINAIS if c not in df.columns]
    if colunas_faltando:
        raise ValueError(f"{os.path.basename(caminho)} sem colunas: {colunas_faltando}")

    df = df[COLUNAS_ORIGINAIS].copy()
    df["nome_coluna_completa"] = limpar_nome_coluna(df)
    df["nome_coluna"] = nome_resumido(df["nome_coluna_completa"])
    df["saldo"] = converter_saldo_br(df["saldo"])

    # Não aceita perder mais de 0,5% dos saldos na conversão numérica
    perdidos = df["saldo"].isna().sum()
    if perdidos / max(len(df), 1) > 0.005:
        raise ValueError(
            f"{os.path.basename(caminho)}: {perdidos}/{len(df)} saldos não convertidos"
        )

    df["cod_inst"] = df["cod_inst"].astype(str).str.strip().str.zfill(8)
    df["ano_mes"] = df["ano_mes"].astype(str).str.strip()
    return df


# ----------------------------------------------------------------------------- #
# 2. Orquestração
# ----------------------------------------------------------------------------- #
def main() -> None:
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    t0 = datetime.now()
    arquivos = sorted(glob.glob(os.path.join(PASTA_ORIGEM, "IFDATA_*.csv")))
    print(f"🔍 {len(arquivos)} arquivos .csv em {PASTA_ORIGEM}")

    formatos = {"snake": 0, "pascal": 0, "outro": 0}
    lista_df, ignorados, erros = [], [], []

    for arquivo in arquivos:
        fmt = detectar_formato(arquivo)
        formatos[fmt] += 1
        if fmt != "outro":
            try:
                df = ler_arquivo_normalizado(arquivo)
                if df is not None:
                    lista_df.append(df)
            except Exception as exc:  # noqa: BLE001 - captura p/ relatório
                erros.append((os.path.basename(arquivo), str(exc)))
        else:
            ignorados.append(os.path.basename(arquivo))

    if not lista_df:
        print("❌ Nenhum arquivo padronizável encontrado. Abortando.")
        sys.exit(1)

    print(f"⚡ Concatenando {len(lista_df)} arquivos "
          f"(snake={formatos['snake']}, pascal={formatos['pascal']}) ...")
    longo = pd.concat(lista_df, ignore_index=True)
    del lista_df

    # ---- Limpeza global ---------------------------------------------------- #
    antes = len(longo)
    longo = longo.dropna(subset=["saldo"])
    n_nan_removidos = antes - len(longo)

    n_dup_chave = longo.duplicated(
        subset=["cod_inst", "ano_mes", "nome_relatorio", "nome_coluna_completa"]
    ).sum()
    if n_dup_chave:
        print(f"⚠️  {n_dup_chave} chaves duplicadas (removidas no pivot).")
    longo = longo.drop_duplicates(
        subset=["cod_inst", "ano_mes", "nome_relatorio", "nome_coluna_completa"]
    )

    validos_ids = longo["cod_inst"].str.fullmatch(r"\d{8}", na=False)
    print(f"✅ Linhas finais: {len(longo)}; ids válidos: {validos_ids.mean():.6f}")

    # ---- Matriz larga (1 linha por instituição/período) -------------------- #
    # Chave SEM colisão: "Relatório | Nome completo da conta".
    # Motivo: 'Ativo Total' existe no Resumo E no Ativo; 'Patrimônio Líquido'
    # na Resumo E no Passivo. Somar sem separar DOBRA os valores
    # (bug encontrado no código anterior do Gemini -> gnn_nodes_features.csv).
    print("📊 Montando painel largo ...")
    longo["chave_larga"] = (
        longo["nome_relatorio"].astype(str) + " | " + longo["nome_coluna_completa"].astype(str)
    )
    wide = (
        longo.pivot_table(index=["cod_inst", "ano_mes"], columns="chave_larga",
                          values="saldo", aggfunc="sum", fill_value=0.0)
        .reset_index()
    )
    wide.columns.name = None

    # ---- Salva -------------------------------------------------------------- #
    longo.to_csv(ARQUIVO_LONGO, index=False, sep=";", compression="gzip")
    wide.to_csv(ARQUIVO_WIDE, index=False, sep=";", encoding="utf-8-sig")
    print(f"💾 Longo (gzip): {ARQUIVO_LONGO}  ({len(longo)} linhas)")
    print(f"💾 Wide (painel): {ARQUIVO_WIDE}  ({wide.shape[0]} x {wide.shape[1]})")

    # ---- Relatório ------------------------------------------------------------ #
    with open(ARQUIVO_RELATORIO, "w", encoding="utf-8") as fh:
        fh.write("=" * 70 + "\n")
        fh.write("RELATÓRIO DE PADRONIZAÇÃO IFData (2000-2024)\n")
        fh.write(f"Gerado em: {t0:%Y-%m-%d %H:%M}\n")
        fh.write("=" * 70 + "\n\n")
        fh.write(f"Arquivos encontrados        : {len(arquivos)}\n")
        fh.write(f"  formato snake (2000-2013)  : {formatos['snake']}\n")
        fh.write(f"  formato pascal (2014-2024) : {formatos['pascal']}\n")
        fh.write(f"  formato ranking (1994-99)  : {formatos['outro']} (fora do escopo)\n\n")
        fh.write(f"Períodos distintos           : {longo['ano_mes'].nunique()}\n")
        fh.write(f"Instituições distintas       : {longo['cod_inst'].nunique()}\n")
        fh.write(f"Registros (conta-inst-período): {len(longo)}\n")
        fh.write(f"Saldo NaN removido           : {n_nan_removidos}\n")
        fh.write(f"Chaves duplicadas no pivot   : {n_dup_chave}\n\n")

        fh.write("Contas por relatório:\n")
        for rel, sub in longo.groupby("nome_relatorio"):
            fh.write(f"  {rel:<28} -> {sub['nome_coluna'].nunique():>3} contas\n")
        fh.write("\nTipo de instituição (por era do arquivo):\n")
        era = np.where(longo["ano_mes"].str[:4].astype(int) < 2014, "2000-2013", "2014-2024")
        for (e, t), n in longo.assign(era=era).groupby(["era", "tipo_instituicao"]).size().items():
            fh.write(f"  {e} -> tipo {t}: {n} registros\n")
        fh.write("\nArquivos ignorados (semestral 1994-1999):\n")
        for nome in ignorados[:60]:
            fh.write(f"  - {nome}\n")
        if len(ignorados) > 60:
            fh.write(f"  ... e mais {len(ignorados) - 60}\n")
        if erros:
            fh.write("\nERROS DE LEITURA:\n")
            for nome, exc in erros:
                fh.write(f"  - {nome}: {exc}\n")
        fh.write("\nFIM\n")
    print(f"📋 Relatório: {ARQUIVO_RELATORIO}")
    print(f"⏱️  Tempo total: {datetime.now() - t0}")


if __name__ == "__main__":
    main()