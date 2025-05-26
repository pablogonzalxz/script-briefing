const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const EventEmitter = require('events');

class WhatsAppService extends EventEmitter {
  constructor() {
    super();
    this.client = new Client({
      authStrategy: new LocalAuth(),
    });
    this.isReady = false;
    this.setupEventHandlers();
  }

  setupEventHandlers() {
    this.client.on('qr', (qr) => {
      console.log('scan QR code:');
      qrcode.generate(qr, { small: true });
    });

    this.client.on('ready', () => {
      console.log('wpp client is ready!');
      this.isReady = true;
      this.emit('ready');
    });

    this.client.on('auth_failure', (msg) => {
      console.error('Authentication failed:', msg);
      this.emit('authFailure', msg);
    });

    this.client.on('disconnected', (reason) => {
      console.log('Client disconnected:', reason);
      this.isReady = false;
      this.emit('disconnected', reason);
    });
  }

  async initialize() {
    try {
      await this.client.initialize();
    } catch (error) {
      console.error('failed to initialize wpp client:', error);
      throw error;
    }
  }

  async sendMessage(to, message) {
    if (!this.isReady) {
      throw new Error('wpp client is not ready');
    }

    try {
      await this.client.sendMessage(to, message);
    } catch (error) {
      console.error('Failed to send message:', error);
      throw new Error(`Failed to send message: ${error.message}`);
    }
  }

  onMessage(handler) {
    this.client.on('message', handler);
  }
}

module.exports = WhatsAppService;