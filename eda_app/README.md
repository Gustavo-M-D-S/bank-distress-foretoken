# IFData - Analise Exploratoria (Streamlit)

App para explorar dados do BCB/IFData (2000-2024) e entender comportamento
das instituicoes financeiras antes de modelar.

## Como rodar

```bash
pip install -r eda_app/requirements.txt
streamlit run eda_app/app.py
```

## Paginas

| Pagina | Conteudo |
|--------|----------|
| Visao Geral | KPI cards, contas por relatorio, cobertura temporal |
| Qualidade | Relatorio de padronizacao, nulos, histograma de saldos |
| Temporal | Evolucao de uma conta ao longo do tempo |
| Indicadores | Alavancagem, ROE, ROA, margem, % credito |
| Correlacao | Heatmap de Pearson + top pares |
| Distribuicao | Histograma, boxplot, skew, kurt, Shapiro-Wilk |
| Concentracao | Top 20, CR4/8/20, HHI, Curva de Lorenz |
| Dados Brutos | Tabela com download CSV (wide/longo) |

## Fontes

- `dados/ifdata_longo_padronizado.csv.gz` (ativo+passivo+resultado em formato longo)
- `dados/ifdata_wide_panel.csv` (painel largo, uma linha por inst-periodo)
- `dados/relatorio_padronizacao.txt` (log do `00_padronizar_dados.py`)

## Problemas conhecidos

- 1994-1999 semestral (fora do escopo)
- 2000-2013: alguns saldos podem ter erro de conversao decimal (virgula vs ponto)
