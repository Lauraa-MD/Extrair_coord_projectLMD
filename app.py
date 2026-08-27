import re

import fitz
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Extrator de coordenadas",
    page_icon="🐟",
    layout="wide"
)


def normalizar_texto(texto):
    substituicoes = {
        "º": "°",
        "˚": "°",
        "′": "'",
        "’": "'",
        "`": "'",
        "″": '"',
        "“": '"',
        "”": '"',
        "−": "-",
        "–": "-"
    }

    for original, novo in substituicoes.items():
        texto = texto.replace(original, novo)

    return texto


def converter_numero(valor):
    return float(valor.replace(",", "."))


def aplicar_hemisferio(valor, hemisferio):
    if hemisferio.upper() in ["S", "W"]:
        return -valor

    return valor


def criar_contexto(texto, inicio, fim):
    margem = 120

    trecho = texto[
        max(0, inicio - margem):
        min(len(texto), fim + margem)
    ]

    return re.sub(r"\s+", " ", trecho).strip()


def extrair_coordenadas(texto, numero_pagina):
    texto = normalizar_texto(texto)

    separador = r"\s*(?:[,;/]\s*|\s+)"

    padroes = [
        {
            "formato": "Graus, minutos e segundos",
            "regex": re.compile(
                rf"(?P<lat_g>\d{{1,2}})\s*°\s*"
                rf"(?P<lat_m>\d{{1,2}})\s*'\s*"
                rf"(?P<lat_s>\d+(?:[.,]\d+)?)\s*\"?\s*"
                rf"(?P<lat_h>[NS])"
                rf"{separador}"
                rf"(?P<lon_g>\d{{1,3}})\s*°\s*"
                rf"(?P<lon_m>\d{{1,2}})\s*'\s*"
                rf"(?P<lon_s>\d+(?:[.,]\d+)?)\s*\"?\s*"
                rf"(?P<lon_h>[EW])",
                re.IGNORECASE
            )
        },
        {
            "formato": "Graus e minutos decimais",
            "regex": re.compile(
                rf"(?P<lat_g>\d{{1,2}})\s*°\s*"
                rf"(?P<lat_m>\d+(?:[.,]\d+)?)\s*'\s*"
                rf"(?P<lat_h>[NS])"
                rf"{separador}"
                rf"(?P<lon_g>\d{{1,3}})\s*°\s*"
                rf"(?P<lon_m>\d+(?:[.,]\d+)?)\s*'\s*"
                rf"(?P<lon_h>[EW])",
                re.IGNORECASE
            )
        },
        {
            "formato": "Graus decimais com hemisfério",
            "regex": re.compile(
                rf"(?P<lat_g>\d{{1,2}}[.,]\d+)\s*°?\s*"
                rf"(?P<lat_h>[NS])"
                rf"{separador}"
                rf"(?P<lon_g>\d{{1,3}}[.,]\d+)\s*°?\s*"
                rf"(?P<lon_h>[EW])",
                re.IGNORECASE
            )
        },
        {
            "formato": "Graus decimais com sinal",
            "regex": re.compile(
                r"(?<![\d.])"
                r"(?P<latitude>[+-]?\d{1,2}\.\d{3,})"
                r"\s*[,;]\s*"
                r"(?P<longitude>[+-]?\d{1,3}\.\d{3,})"
                r"(?![\d.])"
            )
        }
    ]

    resultados = []

    for padrao in padroes:
        for resultado in padrao["regex"].finditer(texto):

            grupos = resultado.groupdict()

            if grupos.get("latitude") is not None:
                latitude = converter_numero(grupos["latitude"])
                longitude = converter_numero(grupos["longitude"])

            else:
                latitude = converter_numero(grupos["lat_g"])
                longitude = converter_numero(grupos["lon_g"])

                if grupos.get("lat_m") is not None:
                    latitude += converter_numero(grupos["lat_m"]) / 60
                    longitude += converter_numero(grupos["lon_m"]) / 60

                if grupos.get("lat_s") is not None:
                    latitude += converter_numero(grupos["lat_s"]) / 3600
                    longitude += converter_numero(grupos["lon_s"]) / 3600

                latitude = aplicar_hemisferio(
                    latitude,
                    grupos["lat_h"]
                )

                longitude = aplicar_hemisferio(
                    longitude,
                    grupos["lon_h"]
                )

            if not (-90 <= latitude <= 90):
                continue

            if not (-180 <= longitude <= 180):
                continue

            resultados.append({
                "Página": numero_pagina,
                "Coordenada original": resultado.group(0),
                "Latitude": round(latitude, 7),
                "Longitude": round(longitude, 7),
                "Formato": padrao["formato"],
                "Contexto": criar_contexto(
                    texto,
                    resultado.start(),
                    resultado.end()
                )
            })

    return resultados


def ler_pdf(arquivo_pdf):
    todos_resultados = []

    documento = fitz.open(
        stream=arquivo_pdf.read(),
        filetype="pdf"
    )

    for numero, pagina in enumerate(documento, start=1):
        texto = pagina.get_text("text")

        resultados_pagina = extrair_coordenadas(
            texto,
            numero
        )

        todos_resultados.extend(resultados_pagina)

    documento.close()

    return todos_resultados


st.title("🐟 Extrator de coordenadas")

st.write(
    "Teste inicial para localizar coordenadas em artigos "
    "científicos e convertê-las para graus decimais."
)

st.warning(
    "Esta versão funciona apenas com PDFs que possuem "
    "texto selecionável. Os resultados devem ser conferidos."
)

arquivo = st.file_uploader(
    "Selecione um artigo em PDF",
    type=["pdf"]
)

if arquivo is not None:

    with st.spinner("Procurando coordenadas no artigo..."):
        resultados = ler_pdf(arquivo)

    if len(resultados) == 0:
        st.warning(
            "Nenhuma coordenada foi encontrada. "
            "O formato pode ainda não estar reconhecido "
            "ou o PDF pode precisar de OCR."
        )

    else:
        tabela = pd.DataFrame(resultados)

        tabela = tabela.drop_duplicates(
            subset=["Página", "Latitude", "Longitude"]
        )

        st.success(
            f"{len(tabela)} coordenada(s) encontrada(s)."
        )

        st.subheader("Coordenadas encontradas")

        st.dataframe(
            tabela,
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Mapa preliminar")

        dados_mapa = tabela.rename(
            columns={
                "Latitude": "lat",
                "Longitude": "lon"
            }
        )

        st.map(dados_mapa[["lat", "lon"]])

        arquivo_csv = tabela.to_csv(
            index=False,
            sep=";",
            decimal=","
        ).encode("utf-8-sig")

        st.download_button(
            label="Baixar resultados em CSV",
            data=arquivo_csv,
            file_name="coordenadas_extraidas.csv",
            mime="text/csv"
        )