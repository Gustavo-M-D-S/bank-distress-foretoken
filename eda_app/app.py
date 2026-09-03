# -*- coding: utf-8 -*-
"""IFData - Analise Exploratoria (2000-2024). Uso: streamlit run eda_app/app.py"""
import os, warnings
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
warnings.filterwarnings("ignore")

st.set_page_config(page_title="IFData EDA", page_icon="\U0001f3db\ufe0f", layout="wide", initial_sidebar_state="expanded")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DADOS = os.path.join(RAIZ, "dados")
ARQ_LONGO = os.path.join(PASTA_DADOS, "ifdata_longo_padronizado.csv.gz")
ARQ_WIDE = os.path.join(PASTA_DADOS, "ifdata_wide_panel.csv")
ARQ_RELATORIO = os.path.join(PASTA_DADOS, "relatorio_padronizacao.txt")

@st.cache_data(ttl=3600, show_spinner="Carregando...")
def carregar_dados():
    longo = pd.read_csv(ARQ_LONGO, sep=";", encoding="utf-8")
    wide = pd.read_csv(ARQ_WIDE, sep=";", encoding="utf-8")
    longo["data"] = pd.to_datetime(longo["ano_mes"].astype(str), format="%Y%m")
    longo["ano"] = longo["data"].dt.year
    longo["trimestre"] = longo["data"].dt.quarter
    wide["data"] = pd.to_datetime(wide["ano_mes"].astype(str), format="%Y%m")
    wide["ano"] = wide["data"].dt.year
    wide["trimestre"] = wide["data"].dt.quarter
    return longo, wide

@st.cache_data(ttl=3600)
def carregar_relatorio():
    if os.path.exists(ARQ_RELATORIO):
        with open(ARQ_RELATORIO, "r", encoding="utf-8") as f:
            return f.read()
    return "Relatorio nao encontrado."

def fmt_brl(v):
    if pd.isna(v): return "N/A"
    if abs(v) >= 1e9: return f"R$ {v/1e9:,.2f} bi"
    if abs(v) >= 1e6: return f"R$ {v/1e6:,.2f} mi"
    if abs(v) >= 1e3: return f"R$ {v/1e3:,.2f} mil"
    return f"R$ {v:,.2f}"

def fmt_num(v):
    if pd.isna(v): return "N/A"
    if isinstance(v, float): return f"{v:,.4f}"
    return f"{v:,}"

def aplicar_filtros(longo, wide):
    st.sidebar.markdown("## \U0001f5a5\ufe0f Filtros")
    anos = sorted(longo["ano"].unique())
    ano_min = st.sidebar.selectbox("Ano inicial", anos, index=0)
    ano_max = st.sidebar.selectbox("Ano final", anos, index=len(anos) - 1)
    tipos = sorted(longo["tipo_instituicao"].dropna().unique())
    tipo_sel = st.sidebar.multiselect("Tipo instituicao", tipos, default=tipos[:5] if len(tipos) > 5 else tipos)
    rels = sorted(longo["nome_relatorio"].unique())
    rel_sel = st.sidebar.multiselect("Relatorio", rels, default=rels)
    mask = (longo["ano"] >= ano_min) & (longo["ano"] <= ano_max) & (longo["nome_relatorio"].isin(rel_sel))
    if tipo_sel:
        mask = mask & (longo["tipo_instituicao"].isin(tipo_sel))
    lf = longo[mask].copy()
    chaves = set(zip(lf["cod_inst"], lf["ano_mes"]))
    wf = wide[wide.apply(lambda r: (r["cod_inst"], r["ano_mes"]) in chaves, axis=1)].copy()
    st.sidebar.markdown(f"**Registros:** {len(lf):,}")
    st.sidebar.markdown(f"**Instituicoes:** {lf['cod_inst'].nunique():,}")
    st.sidebar.markdown(f"**Periodos:** {lf['ano_mes'].nunique()}")
    return lf, wf

def pagina_visao_geral(longo, wide):
    st.markdown("# \U0001f4ca Visao Geral dos Dados")
    st.markdown("---")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Instituicoes", f"{longo['cod_inst'].nunique():,}")
    c2.metric("Periodos", f"{longo['ano_mes'].nunique()}")
    c3.metric("Registros", f"{len(longo):,}")
    c4.metric("Ano inicio", f"{longo['ano'].min()}")
    c5.metric("Ano fim", f"{longo['ano'].max()}")
    st.markdown("---")
    st.markdown("### \U0001f4cb Contas por Relatorio")
    resumo = longo.groupby("nome_relatorio").agg(contas=("nome_coluna", "nunique"), registros=("saldo", "count"), insts=("cod_inst", "nunique")).reset_index().rename(columns={"nome_relatorio": "Relatorio"})
    st.dataframe(resumo, use_container_width=True, hide_index=True)
    st.markdown("### \U0001f3db\ufe0f Tipo de Instituicao")
    tipos = longo["tipo_instituicao"].value_counts().reset_index()
    tipos.columns = ["Tipo", "Quantidade"]
    st.dataframe(tipos, use_container_width=True, hide_index=True)
    st.markdown("### \U0001f4c8 Cobertura Temporal")
    cob = longo.groupby("ano_mes").agg(inst=("cod_inst", "nunique"), regs=("saldo", "count")).reset_index().sort_values("ano_mes")
    cob["periodo"] = cob["ano_mes"].astype(str)
    ca, cb = st.columns(2)
    ca.markdown("**Instituicoes por periodo**")
    ca.bar_chart(cob.set_index("periodo")["inst"])
    cb.markdown("**Registros por periodo**")
    cb.bar_chart(cob.set_index("periodo")["regs"])

def pagina_qualidade(longo, wide):
    st.markdown("# \U0001f50d Qualidade dos Dados")
    st.markdown("---")
    with st.expander("\U0001f4cb Relatorio de Padronizacao", expanded=False):
        st.text(carregar_relatorio())
    st.markdown("---")
    st.markdown("### \u274c Dados Faltantes (formato longo)")
    nulos = longo.isnull().sum().reset_index()
    nulos.columns = ["Coluna", "Nulos"]
    nulos["%"] = (nulos["Nulos"] / len(longo) * 100).round(4)
    nulos = nulos[nulos["Nulos"] > 0].sort_values("Nulos", ascending=False)
    if len(nulos) > 0:
        st.dataframe(nulos, use_container_width=True, hide_index=True)
    else:
        st.success("Nenhum dado faltante!")
    st.markdown("---")
    st.markdown("### \U0001f4b0 Distribuicao de Saldos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldos > 0", f"{(longo['saldo'] > 0).sum():,}")
    c2.metric("Saldos = 0", f"{(longo['saldo'] == 0).sum():,}")
    c3.metric("Saldos < 0", f"{(longo['saldo'] < 0).sum():,}")
    c4.metric("Saldos NaN", f"{longo['saldo'].isna().sum():,}")
    st.markdown("### \U0001f4ca Histograma de Saldos (amostra 50k)")
    import matplotlib.pyplot as plt
    amostra = longo["saldo"].dropna().sample(min(50000, len(longo)), random_state=42)
    q99, q01 = amostra.quantile(0.99), amostra.quantile(0.01)
    af = amostra[(amostra >= q01) & (amostra <= q99)]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(af, bins=100, edgecolor="black", alpha=0.7, color="#2196F3")
    ax.set_xlabel("Saldo (R$ mil)")
    ax.set_ylabel("Frequencia")
    ax.set_title("Distribuicao dos Saldos (percentil 1-99)")
    ax.axvline(0, color="red", linestyle="--", label="Zero")
    ax.legend()
    st.pyplot(fig)
    plt.close()

def pagina_temporal(longo, wide):
    st.markdown("# \U0001f4c8 Analise Temporal")
    st.markdown("---")
    contas = sorted(longo["nome_coluna_completa"].unique())
    conta = st.selectbox("Conta para analise:", contas, index=0)
    dc = longo[longo["nome_coluna_completa"] == conta].copy()
    if len(dc) == 0:
        st.warning("Nenhum dado para esta conta.")
        return
    st.markdown(f"**Conta:** {conta} | **Registros:** {len(dc):,}")
    st.markdown("### \U0001f4ca Evolucao por periodo")
    st_t = dc.groupby("ano_mes")["saldo"].agg(["mean", "median", "std", "count", "sum"]).reset_index().sort_values("ano_mes")
    st_t.columns = ["Periodo", "Media", "Mediana", "Desvio", "N Obs", "Soma"]
    ca, cb = st.columns(2)
    ca.markdown("**Media e Mediana**")
    ca.line_chart(st_t.set_index("Periodo")[["Media", "Mediana"]])
    cb.markdown("**Numero de observacoes**")
    cb.bar_chart(st_t.set_index("Periodo")[["N Obs"]])
    with st.expander("Tabela de estatisticas"):
        st.dataframe(st_t, use_container_width=True, hide_index=True)
    st.markdown("### \U0001f3c6 Top 10 (periodo mais recente)")
    pr = dc["ano_mes"].max()
    top = dc[dc["ano_mes"] == pr].nlargest(10, "saldo")[["cod_inst", "saldo", "tipo_instituicao"]].reset_index(drop=True)
    top.columns = ["Cod Inst", "Saldo", "Tipo"]
    top["Saldo"] = top["Saldo"].apply(fmt_brl)
    st.dataframe(top, use_container_width=True, hide_index=True)

def pagina_indicadores(longo, wide):
    st.markdown("# \U0001f4b0 Indicadores Financeiros")
    st.markdown("---")
    cols = [c for c in wide.columns if c not in ["cod_inst", "ano_mes", "data", "ano", "trimestre"]]
    st.markdown(f"**{len(cols)} colunas disponiveis no painel largo.**")
    with st.expander("Ver colunas"):
        for c in cols:
            st.code(c)
    st.markdown("---")
    ca = [c for c in cols if "Ativo Total" in c and "Ajustado" not in c]
    cp = [c for c in cols if "Patrim" in c and "Liqu" in c]
    cps = [c for c in cols if "Passivo Total" in c]
    cl = [c for c in cols if "Lucro" in c or "Resultado" in c]
    cr = [c for c in cols if "Receitas de Intermedia" in c]
    cd = [c for c in cols if "Despesas de Intermedia" in c]
    cc = [c for c in cols if "Opera" in c and "Credito" in c and "Liqu" in c]
    cdep = [c for c in cols if "Deposito Total" in c]
    wc = wide.copy()
    if ca: wc["ativo"] = wc[ca[0]]
    if cp: wc["pat"] = wc[cp[0]]
    if cps: wc["pass"] = wc[cps[0]]
    if cl: wc["res"] = wc[cl[0]]
    if cr: wc["rec"] = wc[cr[0]]
    if cd: wc["des"] = wc[cd[0]]
    if cc: wc["oc"] = wc[cc[0]]
    if cdep: wc["dep"] = wc[cdep[0]]
    inds = []
    if "ativo" in wc and "pat" in wc:
        wc["alav"] = np.where(wc["pat"] != 0, wc["ativo"] / wc["pat"], np.nan); inds.append("alav")
    if "res" in wc and "pat" in wc:
        wc["roe"] = np.where(wc["pat"] != 0, wc["res"] / wc["pat"] * 100, np.nan); inds.append("roe")
    if "res" in wc and "ativo" in wc:
        wc["roa"] = np.where(wc["ativo"] != 0, wc["res"] / wc["ativo"] * 100, np.nan); inds.append("roa")
    if "rec" in wc and "des" in wc:
        wc["marg"] = np.where(wc["rec"] != 0, (wc["rec"] + wc["des"]) / wc["rec"] * 100, np.nan); inds.append("marg")
    if "oc" in wc and "ativo" in wc:
        wc["pcred"] = np.where(wc["ativo"] != 0, wc["oc"] / wc["ativo"] * 100, np.nan); inds.append("pcred")
    if not inds:
        st.warning("Nao foi possivel calcular indicadores.")
        return
    st.markdown("### \U0001f4ca Estatisticas")
    st.dataframe(wc[inds].describe().T, use_container_width=True)
    st.markdown("### \U0001f4c8 Evolucao")
    ev = wc.groupby("ano")[inds].mean().reset_index()
    ip = st.selectbox("Indicador:", inds)
    ca, cb = st.columns(2)
    ca.line_chart(ev.set_index("ano")[[ip]])
    cb.dataframe(ev[["ano", ip]].rename(columns={"ano": "Ano"}), use_container_width=True, hide_index=True)

def pagina_correlacao(longo, wide):
    st.markdown("# \U0001f517 Correlacao")
    st.markdown("---")
    cols = [c for c in wide.columns if c not in ["cod_inst", "ano_mes", "data", "ano", "trimestre"]]
    sel = st.multiselect("Colunas:", cols, default=cols[:8] if len(cols) >= 8 else cols)
    if len(sel) < 2:
        st.warning("Selecione pelo menos 2 colunas.")
        return
    dc = wide[sel].dropna()
    st.markdown(f"**{len(dc):,} observacoes validas.**")
    cm = dc.corr()
    import matplotlib.pyplot as plt
    import seaborn as sns
    fig, ax = plt.subplots(figsize=(max(8, len(sel)), max(6, len(sel) * 0.7)))
    sns.heatmap(cm, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1, square=True, linewidths=0.5, ax=ax)
    ax.set_title("Correlacao de Pearson")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
    pares = []
    for i in range(len(cm.columns)):
        for j in range(i + 1, len(cm.columns)):
            pares.append({"V1": cm.columns[i], "V2": cm.columns[j], "R": cm.iloc[i, j]})
    pdf = pd.DataFrame(pares)
    pdf["A"] = pdf["R"].abs()
    pdf = pdf.sort_values("A", ascending=False).head(20).drop(columns=["A"])
    st.dataframe(pdf, use_container_width=True, hide_index=True)

def pagina_distribuicao(longo, wide):
    st.markdown("# \U0001f4ca Distribuicao")
    st.markdown("---")
    rels = sorted(longo["nome_relatorio"].unique())
    rel = st.selectbox("Relatorio:", rels)
    contas = sorted(longo[longo["nome_relatorio"] == rel]["nome_coluna_completa"].unique())
    conta = st.selectbox("Conta:", contas)
    dados = longo[(longo["nome_relatorio"] == rel) & (longo["nome_coluna_completa"] == conta)]["saldo"].dropna()
    inc = st.checkbox("Incluir zeros", value=True)
    if not inc:
        dados = dados[dados != 0]
    if len(dados) == 0:
        st.warning("Sem dados.")
        return
    q99, q01 = dados.quantile(0.99), dados.quantile(0.01)
    q95, q05 = dados.quantile(0.95), dados.quantile(0.05)
    ls = st.slider("Limite sup", int(q05), int(q99 * 1.5), int(q95))
    li = st.slider("Limite inf", int(q01 * 1.5), int(q95), int(q05))
    df_ = dados[(dados >= li) & (dados <= ls)]
    import matplotlib.pyplot as plt
    from scipy import stats as sp
    c1, c2 = st.columns(2)
    with c1:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(df_, bins=80, edgecolor="black", alpha=0.7, color="#4CAF50", density=True)
        ax.set_xlabel("Saldo (R$ mil)")
        ax.set_ylabel("Densidade")
        ax.set_title(f"Histograma - {conta[:40]}")
        ax.axvline(df_.mean(), color="red", linestyle="--", label=f"Media: {fmt_brl(df_.mean())}")
        ax.axvline(df_.median(), color="blue", linestyle="--", label=f"Mediana: {fmt_brl(df_.median())}")
        ax.legend(fontsize=8)
        st.pyplot(fig)
        plt.close()
    with c2:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.boxplot(df_, vert=True)
        ax.set_ylabel("Saldo (R$ mil)")
        ax.set_title(f"Boxplot - {conta[:40]}")
        st.pyplot(fig)
        plt.close()
    st.markdown("### Estatisticas")
    ca, cb, cc, cd, ce = st.columns(5)
    ca.metric("N", fmt_num(len(df_)))
    cb.metric("Media", fmt_brl(df_.mean()))
    cc.metric("Mediana", fmt_brl(df_.median()))
    cd.metric("Desvio", fmt_brl(df_.std()))
    cv = f"{df_.std()/df_.mean()*100:.2f}%" if df_.mean() != 0 else "N/A"
    ce.metric("CV", cv)
    cf, cg = st.columns(2)
    cf.metric("Skew", f"{sp.skew(df_):.4f}")
    cg.metric("Kurt", f"{sp.kurtosis(df_):.4f}")
    if len(df_) >= 20:
        sw_s, sw_p = sp.shapiro(df_.sample(min(5000, len(df_)), random_state=42))
        st.markdown(f"**Shapiro-Wilk:** stat={sw_s:.4f}, p={sw_p:.6f}")
        st.info("NAO normal (p<0.05)" if sw_p < 0.05 else "Normal (p>=0.05)")

def pagina_concentracao(longo, wide):
    st.markdown("# \U0001f3c6 Concentracao")
    st.markdown("---")
    cols = [c for c in wide.columns if c not in ["cod_inst", "ano_mes", "data", "ano", "trimestre"]]
    var = st.selectbox("Variavel:", cols, index=0)
    per = sorted(wide["ano_mes"].unique())
    periodo = st.selectbox("Periodo:", per, index=len(per) - 1)
    dp = wide[wide["ano_mes"] == periodo][["cod_inst", var]].dropna()
    dp = dp[dp[var] > 0].sort_values(var, ascending=False)
    if len(dp) == 0:
        st.warning("Sem dados.")
        return
    st.markdown(f"**{periodo} | {len(dp):,} instituicoes**")
    st.markdown("### Top 20")
    t20 = dp.head(20).reset_index(drop=True)
    t20.index = t20.index + 1
    t20.columns = ["Cod", var]
    st.dataframe(t20, use_container_width=True)
    vals = dp[var].values
    total = vals.sum()
    st.markdown("### Indices")
    if total > 0:
        cr4 = vals[:4].sum() / total * 100 if len(vals) >= 4 else 100
        cr8 = vals[:8].sum() / total * 100 if len(vals) >= 8 else 100
        cr20 = vals[:20].sum() / total * 100 if len(vals) >= 20 else 100
        hhi = ((vals / total) ** 2).sum() * 10000
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CR4", f"{cr4:.2f}%")
        c2.metric("CR8", f"{cr8:.2f}%")
        c3.metric("CR20", f"{cr20:.2f}%")
        c4.metric("HHI", f"{hhi:,.0f}")
        st.caption("HHI: <1500 pouco | 1500-2500 moderado | >2500 alto")
    import matplotlib.pyplot as plt
    st.markdown("### Curva de Lorenz")
    n = len(vals)
    lorenz = np.cumsum(np.sort(vals)) / total
    pct = np.arange(1, n + 1) / n
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(pct, lorenz, label="Lorenz", color="#2196F3")
    ax.plot([0, 1], [0, 1], "r--", label="Igualdade")
    ax.fill_between(pct, lorenz, pct, alpha=0.2, color="gray")
    ax.set_xlabel("% Instituicoes")
    ax.set_ylabel("% Variavel")
    ax.set_title(f"Lorenz - {var[:50]} ({periodo})")
    ax.legend()
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)
    plt.close()
    st.markdown("### Evolucao")
    evc = []
    for p in per:
        dp2 = wide[wide["ano_mes"] == p][["cod_inst", var]].dropna()
        dp2 = dp2[dp2[var] > 0].sort_values(var, ascending=False)
        v = dp2[var].values
        t = v.sum()
        if t > 0 and len(v) >= 4:
            evc.append({"P": p, "CR4": v[:4].sum() / t * 100, "HHI": ((v / t)**2).sum() * 10000})
    if evc:
        ef = pd.DataFrame(evc)
        cx, cy = st.columns(2)
        cx.line_chart(ef.set_index("P")[["CR4"]])
        cy.line_chart(ef.set_index("P")[["HHI"]])

def pagina_dados_brutos(longo, wide):
    st.markdown("# \U0001f4cb Dados Brutos")
    st.markdown("---")
    aba = st.radio("Formato:", ["Wide", "Longo"], horizontal=True)
    if aba == "Wide":
        st.markdown(f"**{wide.shape[0]:,} x {wide.shape[1]}**")
        cls = list(wide.columns)
        sel = st.multiselect("Colunas:", cls, default=cls[:15])
        if not sel: sel = cls[:15]
        fi = st.text_input("Filtrar cod_inst:")
        d = wide[sel].copy()
        if fi: d = d[wide["cod_inst"].astype(str).str.contains(fi)]
        st.dataframe(d, use_container_width=True, height=500)
        st.download_button("CSV", d.to_csv(index=False, sep=";").encode("utf-8"), "wide.csv", "text/csv")
    else:
        st.markdown(f"**{longo.shape[0]:,} x {longo.shape[1]}**")
        r1, r2 = st.columns(2)
        fr = r1.multiselect("Relatorio:", sorted(longo["nome_relatorio"].unique()))
        fi = r2.text_input("Filtrar cod_inst:")
        d = longo.copy()
        if fr: d = d[d["nome_relatorio"].isin(fr)]
        if fi: d = d[d["cod_inst"].astype(str).str.contains(fi)]
        if len(d) > 100000:
            st.warning(f"100k de {len(d):,}")
            d = d.head(100000)
        st.dataframe(d, use_container_width=True, height=500)
        st.download_button("CSV", d.to_csv(index=False, sep=";").encode("utf-8"), "longo.csv", "text/csv")

def pagina_sobre():
    st.markdown("# \u2139\ufe0f Sobre")
    st.markdown(""" **IFData - Analise Exploratoria (BCB 2000-2024)**
    - 2000-2013: BacenR (snake_case, decimal virgula)
    - 2014-2024: API Olinda (PascalCase, decimal ponto)
    - 1994-1999: Semestral (fora do escopo)
    - Ativo: 16 contas | Passivo: 23 | Resultado: 30
    - Problema: saldos 2000-2013 com erro de conversao decimal
    """)

def main():
    st.markdown("## \U0001f3db\ufe0f IFData - Analise Exploratoria")
    st.markdown("*BCB 2000-2024*")
    try:
        longo, wide = carregar_dados()
    except Exception as e:
        st.error(f"Erro: {e}")
        return
    st.sidebar.markdown("---")
    st.sidebar.markdown("## \U0001f4c2 Navegacao")
    pags = {"\U0001f4ca Visao Geral": pagina_visao_geral, "\U0001f50d Qualidade": pagina_qualidade,
            "\U0001f4c8 Temporal": pagina_temporal, "\U0001f4b0 Indicadores": pagina_indicadores,
            "\U0001f517 Correlacao": pagina_correlacao, "\U0001f4ca Distribuicao": pagina_distribuicao,
            "\U0001f3c6 Concentracao": pagina_concentracao, "\U0001f4cb Dados Brutos": pagina_dados_brutos,
            "\u2139\ufe0f Sobre": pagina_sobre}
    pag = st.sidebar.radio("Ir para:", list(pags.keys()))
    if pag == "\u2139\ufe0f Sobre":
        pagina_sobre()
    else:
        lf, wf = aplicar_filtros(longo, wide)
        pags[pag](lf, wf)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"\u23f1\ufe0f {datetime.now().strftime('%H:%M:%S')} | v1.0")

if __name__ == "__main__":
    main()
