# Instalar pacotes necessários (descomente a linha abaixo se ainda não tiver o dplyr)
# install.packages("dplyr")

# Carregar os pacotes
library(bacenR)
library(dplyr)

# 1. Configurações do que queremos baixar
anos <- 2000:2014
meses <- c(3, 6, 9, 12) # Trimestres (março, junho, setembro, dezembro)
tipo_inst <- 2          # 1 = Conglomerados Prudenciais e Instituições Independentes

# Dicionário dos relatórios
relatorios <- list(
  "Resumo" = 1,
  "Ativo" = 2,
  "Passivo" = 3,
  "Resultado" = 4
)

# 2. Criar uma pasta no seu computador para guardar os arquivos
pasta_destino <- "IFDATA_bacenR_2000_2014"
if (!dir.exists(pasta_destino)) {
  dir.create(pasta_destino)
}

# 3. Loop Mágico: Passar por cada ano, mês e relatório
for (ano in anos) {
  for (mes in meses) {
    for (nome_relatorio in names(relatorios)) {
      num_relatorio <- relatorios[[nome_relatorio]]
      
      # Print no console para você acompanhar o que está acontecendo
      cat(sprintf("\n➡️  Tentando baixar: %d-M%02d | Relatório: %s\n", ano, mes, nome_relatorio))
      
      # O tryCatch protege o código de "quebrar" se o BCB não tiver o arquivo do ano 2000
      dados <- tryCatch({
        get_ifdata_reports(
          year = ano,
          month = mes,
          type_institution = tipo_inst,
          report = num_relatorio,
          verbose = FALSE # Deixa o console mais limpo
        )
      }, error = function(e) {
        cat("   ❌ Dado inexistente no servidor do BCB para esta data.\n")
        return(NULL) # Retorna vazio e segue a vida
      })
      
      # 4. Salvar o arquivo se o dado existir
      if (!is.null(dados) && nrow(dados) > 0) {
        # Monta o nome do arquivo, ex: IFDATA_201312_Ativo.csv
        nome_arquivo <- sprintf("%s/IFDATA_%d%02d_%s.csv", pasta_destino, ano, mes, nome_relatorio)
        
        # Salva em CSV com separador ponto e vírgula, padrão Brasil
        write.table(
          x = dados, 
          file = nome_arquivo, 
          sep = ";", 
          row.names = FALSE, 
          fileEncoding = "UTF-8"
        )
        
        cat(sprintf("   ✅ Sucesso! Salvo em: %s (%d linhas)\n", nome_arquivo, nrow(dados)))
      }
      
      # Uma pequena pausa de 1 segundo para não tomar bloqueio do servidor do Banco Central
      Sys.sleep(1)
    }
  }
}

cat("\n🎉 EXTRAÇÃO CONCLUÍDA! Verifique a pasta:", pasta_destino, "\n")