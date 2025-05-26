# Script Briefing

## Visão Geral

Este projeto foi criado para ajudar influenciadores a automatizar a criação de roteiros publicitários para marcas, que muitas vezes possuem briefings muito restritivos e com pouco espaço para criatividade. A ideia principal é usar IA para gerar roteiros que respeitem o estilo único de cada influenciador, economizando tempo e esforço.

Apesar das limitações das marcas, esse sistema mantém o toque pessoal do influenciador usando roteiros antigos como contexto e memória, melhorando a naturalidade e personalização dos roteiros gerados.

---

## Objetivos do Projeto

* Facilitar e acelerar a criação de roteiros publicitários baseados em briefings recebidos.
* Preservar o estilo e a voz do influenciador usando aprendizado a partir de roteiros anteriores.
* Integrar comunicação via WhatsApp para envio e recebimento de roteiros.

---

## Tecnologias Utilizadas

* **Python com FastAPI** — Backend e lógica principal do projeto.
* **OpenAI** — Geração de texto com IA.
* **Langchain** — Chamadas ao modelo, embeddings, agentes e RAG (Retrieval-Augmented Generation).
* **Chroma** — Banco vetorial para armazenamento e busca contextual de roteiros antigos.
* **Node.js + whatsapp-web.js** — Serviço de mensageria entre o Python e o Whatsapp.
* **Controle de uso por plano** — Gerenciamento de limites para usuários "Free" e pagos.

---

## Como Funciona

1. **Recebimento de briefings e roteiros antigos:** O influenciador envia o briefing da marca e pode também enviar roteiros antigos que ele escreveu para que o sistema use de contexto o estilo de conteúdo dele.
2. **Contextualização com embeddings:** O sistema utiliza comparação vetorial para buscar roteiros similares do usuário e entender o contexto.
3. **Geração do roteiro:** Com base no briefing e contexto, o modelo gera um roteiro personalizado, mantendo o estilo do influenciador.
4. **Envio via WhatsApp:** O roteiro é enviado diretamente para o influenciador via Whatsapp.

---

## Principais Conceitos e Aprendizados

* **Large Language Models (LLM):** Aprender a aplicar GPT-4 em um caso de uso real.
* **Embeddings e Vector Stores:** Uso de Chroma para guardar e consultar memória de roteiros antigos.
* **RAG (Retrieval-Augmented Generation):** Técnica para gerar respostas mais contextualizadas e relevantes.
* **Gestão de limites:** Criar controle de uso para diferentes planos de usuário.

---

## Próximos Passos

* Integração com e-mails para gerar roteiros automaticamente a partir do título da mensagem.
* Desenvolvimento de um site para facilitar o feedback e o acompanhamento dos roteiros.
* Implementação de aprendizado contínuo com base no feedback do usuário.
* Análise automática de métricas da conta do influenciador para detectar padrões de sucesso.
