const express = require('express');
const bodyParser = require('body-parser');
const config = require('./config');
const WhatsAppService = require('./services/wppService');
const MessageProcessor = require('./services/msgProcessor');
const createMessageRoutes = require('./routes/msgRoutes');

class WhatsAppBot {
  constructor() {
    this.app = express();
    this.whatsappService = new WhatsAppService();
    this.messageProcessor = new MessageProcessor(this.whatsappService);
    
    this.setupMiddleware();
    this.setupRoutes();
    this.setupMessageHandlers();
  }

  setupMiddleware() {
    this.app.use(bodyParser.json({ limit: '10mb' }));
    this.app.use(express.static('public'));
  }

  setupRoutes() {
    this.app.use('/', createMessageRoutes(this.whatsappService));
    
    this.app.get('/health', (req, res) => {
      res.json({ status: 'ok', timestamp: new Date().toISOString() });
    });
  }

  setupMessageHandlers() {
    this.whatsappService.onMessage(async (msg) => {
      await this.messageProcessor.processMessage(msg);
    });
  }

  async start() {
    try {
      await this.whatsappService.initialize();

      this.whatsappService.once('ready', () => {
        this.app.listen(config.port, () => {
          console.log(`server running on port ${config.port}`);
          console.log(`health check: http://localhost:${config.port}/health`);
        });
      });
      
    } catch (error) {
      console.error('Failed to start:', error);
      process.exit(1);
    }
  }
}

const bot = new WhatsAppBot();
bot.start();