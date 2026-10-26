import json
import os
from datetime import datetime
from typing import Dict, Optional, Union
import google.generativeai as genai
from PIL import Image

from config import (
    GEMINI_API_KEY,
    CENTROS_DE_CUSTO,
    CATEGORIAS_PADRAO,
    CARTOES_PADRAO
)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-3.5-flash"

SYSTEM_PROMPT_PARSER = f"""
Você é um agente assistente financeiro pessoal e corporativo de altíssima precisão.
Seu trabalho é extrair dados de despesas ou receitas enviadas pelo usuário (por texto, áudio transcrito ou imagem de comprovante).

Existem exatamente 3 CENTROS DE CUSTO:
1. "Casa" (Gastos pessoais, família, mercado, moradia pessoal, lazer, etc.)
2. "Consultório" (Despesas clínicas/médicas/odontológicas, insumos de saúde, secretária, aluguel da clínica, CRO/CRM, etc.)
3. "D-CAD" (Despesas da empresa de tecnologia / desenho CAD/CAM / prótese digital, licenças de software, blocos de fresagem, impressora 3D, servidores, etc.)

Cartões de crédito conhecidos por centro de custo:
{json.dumps([c['cartao'] + ' (' + c['centro_custo'] + ')' for c in CARTOES_PADRAO], ensure_ascii=False, indent=2)}

Categorias sugeridas:
{json.dumps(CATEGORIAS_PADRAO, ensure_ascii=False, indent=2)}

Sua resposta DEVE SER EXCLUSIVAMENTE um objeto JSON válido, sem crases de código markdown, sem texto antes ou depois, seguindo esta estrutura:
{{
  "centro_custo": "Casa" | "Consultório" | "D-CAD" | "Indefinido",
  "confianca_centro_custo": true | false,
  "tipo": "Despesa" | "Receita",
  "valor": 0.00,
  "categoria": "Nome da Categoria",
  "descricao": "Descrição clara e concisa do gasto",
  "forma_pagamento": "Cartão de Crédito" | "Cartão de Débito" | "Pix" | "Boleto" | "Dinheiro" | "Transferência" | "Não especificado",
  "cartao": "Nome do cartão se for Cartão de Crédito (ex: Nubank Casa, Itaú Casa, Inter Consultório, Bradesco D-CAD PJ) ou N/A",
  "parcelas": "À vista" | "2x" | "3x" | "4x" | "5x" | "6x" | "10x" | "12x" | ...,
  "data": "AAAA-MM-DD" (se o usuário disser ontem/semana passada calcule com base na data de hoje; senão use a data de hoje),
  "observacao": "Alguma observação relevante extraída"
}}

Regras importantes:
- O campo "valor" deve ser SEMPRE um número float puro com ponto decimal (ex: 35.50 para R$ 35,50; 1200.00 para R$ 1.200,00). NUNCA multiplique centavos por 100 ou 1000!
- Se a forma de pagamento for cartão de crédito:
  * Identifique qual cartão foi citado (ex: "no Nubank", "no Itaú", "no Inter", "no Bradesco", "cartão PJ").
  * Se não for citado o nome do banco mas disser "no cartão do consultório", escolha o cartão daquele centro de custo.
  * Se não for citado, coloque o cartão padrão correspondente ao centro de custo.
  * Se a compra for parcelada (ex: "em 3 vezes", "parcelado em 5x", "10x"), defina o campo "parcelas" com "3x", "5x", etc. Se não mencionar parcelamento, use "À vista".
- Se NÃO for cartão de crédito, defina "cartao": "N/A" e "parcelas": "À vista".
- Se o usuário não mencionar explicitamente o centro de custo e não for óbvio pelo contexto (ex: "gastei 50 no almoço"), defina "centro_custo": "Indefinido" e "confianca_centro_custo": false.
- Se for termo médico/clínico (resina, anestésico, autoclave, jaleco, CRO), classifique como "Consultório" com confianca_centro_custo: true.
- Se for termo CAD/CAM (exocad, 3shape, fresadora, zircônia, STL, filamento 3D), classifique como "D-CAD" com confianca_centro_custo: true.
"""

class FinancialAIAgent:
    def __init__(self):
        # Suporta tanto chave do .env quanto st.secrets do Streamlit Cloud
        api_key = GEMINI_API_KEY
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            pass

        if not api_key:
            self.model = None
            return

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_PROMPT_PARSER
        )

    def _clean_json_response(self, text: str) -> Dict:
        """Limpa blocos de código e formata para dicionário."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback seguro
            return {
                "centro_custo": "Indefinido",
                "confianca_centro_custo": false,
                "tipo": "Despesa",
                "valor": 0.0,
                "categoria": "Outros",
                "descricao": text[:100],
                "forma_pagamento": "Não especificado",
                "data": datetime.now().strftime("%Y-%m-%d"),
                "observacao": "Erro ao decodificar JSON gerado pela IA"
            }

    def parse_text(self, text: str) -> Dict:
        """Processa texto enviado pelo usuário no Telegram."""
        if not self.model:
            raise ValueError("GEMINI_API_KEY não configurada.")

        hoje = datetime.now().strftime("%Y-%m-%d")
        prompt = f"Data de hoje: {hoje}\nMensagem do usuário: {text}"
        response = self.model.generate_content(prompt)
        return self._clean_json_response(response.text)

    def parse_image(self, image_path: str, user_caption: Optional[str] = None) -> Dict:
        """Processa foto ou imagem de comprovante/recibo."""
        if not self.model:
            raise ValueError("GEMINI_API_KEY não configurada.")

        hoje = datetime.now().strftime("%Y-%m-%d")
        img = Image.open(image_path)
        prompt = [
            f"Data de hoje: {hoje}\nAnalise esta imagem de comprovante ou nota fiscal e extraia os dados financeiros.",
            img
        ]
        if user_caption:
            prompt.append(f"Legenda enviada pelo usuário: {user_caption}")

        response = self.model.generate_content(prompt)
        return self._clean_json_response(response.text)

    def parse_audio(self, audio_file_path: str) -> Dict:
        """Transcreve e processa mensagem de áudio enviada no Telegram."""
        if not self.model:
            raise ValueError("GEMINI_API_KEY não configurada.")

        hoje = datetime.now().strftime("%Y-%m-%d")
        # Faz upload do arquivo para a API do Gemini
        uploaded_file = genai.upload_file(path=audio_file_path)
        prompt = [
            f"Data de hoje: {hoje}\nOuça este áudio do usuário, transcreva mentalmente o que ele disse e extraia a transação financeira no formato JSON definido nas instruções.",
            uploaded_file
        ]
        response = self.model.generate_content(prompt)
        return self._clean_json_response(response.text)

    def generate_analysis(self, transactions_summary_text: str) -> str:
        """Gera análise financeira e recomendações com base no resumo das transações."""
        if not self.model:
            return "Chave Gemini não configurada para gerar análises."

        prompt = f"""
Você é um consultor financeiro de alto nível.
Analise os dados financeiros abaixo (que englobam os centros de custo 'Casa', 'Consultório' e 'D-CAD') e forneça um relatório executivo conciso, direto e estratégico em Markdown:

Dados:
{transactions_summary_text}

Sua resposta deve conter:
1. 📊 **Visão Geral & Destaques**: Principais números e onde está o maior volume financeiro.
2. 🏥 **Diagnóstico Consultório**: Eficiência operacional, custos com insumos e equipe.
3. 💻 **Diagnóstico D-CAD**: Rentabilidade, impacto de licenças e maquinário.
4. 🏠 **Diagnóstico Casa**: Saúde financeira pessoal e taxa de poupança/investimento.
5. 💡 **3 Recomendações Práticas Imediatas**: O que fazer para otimizar os gastos no próximo ciclo.
"""
        response = self.model.generate_content(prompt)
        return response.text
