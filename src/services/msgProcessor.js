const axios = require('axios');
const path = require('path');
const fs = require('fs').promises;
const config = require('../config');
const { getExtensionFromMimeType, sanitizeFilename, ensureDirectoryExists } = require('../utils/fileUtils');

class MessageProcessor {
  constructor(whatsappService) {
    this.whatsappService = whatsappService;
    this.setupUploadsDirectory();
  }

  async setupUploadsDirectory() {
    await ensureDirectoryExists(config.uploadsDir);
  }

  async processMessage(msg) {
    try {
      console.log(`received message from ${msg.from}: ${msg.body || '[no text]'}`);
      
      let messagePayload = {
        from: msg.from,
        type: msg.type,
        timestamp: msg.timestamp,
        id: msg.id._serialized
      };

      if (msg.type === 'document') {
        messagePayload = await this.processDocument(msg, messagePayload);
      } else if (msg.body) {
        messagePayload.text = msg.body;
      }

      const response = await this.sendToWebhook(messagePayload);
      
      if (response) {
        await this.handleResponse(response);
      }

    } catch (error) {
      console.error('error processing message:', error);
      if (msg.from) {
        await this.whatsappService.sendMessage(
          msg.from, 
          '❌ Ocorreu um erro ao processar sua mensagem. Tente novamente em alguns minutos.'
        );
      }
    }
  }

  async handleResponse(response) {
    const { status, user_id, message, user_stats, command, script } = response;

    switch (status) {
      case 'text_received':
        await this.handleTextMessage(user_id, command, user_stats);
        break;
      
      case 'rate_limited':
        await this.whatsappService.sendMessage(user_id, message);
        break;
      
      case 'error':
        await this.whatsappService.sendMessage(user_id, '❌ Arquivo não encontrado.');
        break;
      
      case 'script_received':
        await this.whatsappService.sendMessage(user_id, 'Contexto recebido e armazenado com sucesso, será usado nos próximos roteiros que eu gerar p vc!');
        break;
      
      case 'doc_processed':
        await this.whatsappService.sendMessage(user_id, 'Processando seu documento... Aguarde um momento.');
        await this.whatsappService.sendMessage(user_id, `Roteiro gerado com sucesso!\n\n${script}`);
        break;
      
      default:
        console.log('Unhandled response status:', status);
    }
  }

  async handleTextMessage(user_id, command, user_stats) {
    const { daily_remaining, monthly_remaining, daily_used, daily_total, monthly_used, monthly_total, is_premium, created_at } = user_stats;

    switch (command) {
      case '/stats':
        const statsMessage = `📊 Suas Estatísticas:
📅 Uso Diário: ${daily_used}/${daily_total} (restam ${daily_remaining})
📆 Uso Mensal: ${monthly_used}/${monthly_total} (restam ${monthly_remaining})
👑 Me fez o pix?: ${is_premium ? 'Sim ✅' : 'Não ❌'}
📅 Membro desde: ${created_at.substring(0, 10)}`;
        await this.whatsappService.sendMessage(user_id, statsMessage);
        break;

      case '/help':
        const helpMessage = `Comandos Disponíveis:
/stats - Ver suas estatísticas de uso
/help - Ver esta mensagem de ajuda

Seus Limites Atuais:
📅 Diário: ${daily_remaining} mensagens restantes hoje
📆 Mensal: ${monthly_remaining} mensagens restantes este mês

Como usar:
• Envie briefings que eu gero seu roteiro
• Você tem limites diários e mensais de uso
• Entre em contato com o suporte para upgrade premium`;
        await this.whatsappService.sendMessage(user_id, helpMessage);
        break;

      default:
        const usageMessage = `Eae, beleza? 

Seus limites atuais:
Hoje: ${daily_remaining} de ${daily_total} disponíveis
Este mês: ${monthly_remaining} de ${monthly_total} disponíveis

Para usar o bot:
• Envie um briefing que eu gero o roteiro p vc!
• Digite /stats para ver estatísticas detalhadas  
• Digite /help para ver todos os comandos`;
        await this.whatsappService.sendMessage(user_id, usageMessage);
    }
  }

  async processDocument(msg, messagePayload) {
    try {
      const attachmentData = await msg.downloadMedia();
      
      if (attachmentData.data.length > config.maxFileSize) {
        throw new Error('File size exceeds maximum allowed size');
      }

      const fileBuffer = Buffer.from(attachmentData.data, 'base64');
      
      let fileName = msg.body || `document_${Date.now()}`;
      fileName = sanitizeFilename(fileName);
      
      if (!path.extname(fileName)) {
        const ext = getExtensionFromMimeType(msg.mimetype);
        fileName += ext;
      }

      const filePath = path.resolve(config.uploadsDir, fileName);
      await fs.writeFile(filePath, fileBuffer);

      return {
        ...messagePayload,
        type: "document",
        document: {
          id: msg.id._serialized,
          mimeType: msg.mimetype,
          filename: fileName,
          filePath: filePath,
          size: fileBuffer.length
        }
      };
    } catch (error) {
      console.error('Error processing document:', error);
      throw error;
    }
  }

  async sendToWebhook(messagePayload) {
    const webhookPayload = {
      entry: [{
        changes: [{
          value: {
            messages: [messagePayload]
          }
        }]
      }]
    };

    try {
      const response = await axios.post(config.webhookUrl, webhookPayload, {
        timeout: 80000,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      return response.data;
    } catch (error) {
      console.error('Error sending to webhook:', error.message);
      throw error;
    }
  }

  async getUserStats(userId) {
    try {
      const response = await axios.get(`${config.pythonBackendUrl}/user_stats/${userId}`, {
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      return response.data;
    } catch (error) {
      console.error('Error getting user stats:', error.message);
      return null;
    }
  }
}

module.exports = MessageProcessor;