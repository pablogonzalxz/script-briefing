require('dotenv').config();

module.exports = {
  port: process.env.PORT || 3000,
  webhookUrl: process.env.WEBHOOK_URL || 'http://localhost:5000/receive_webhook',
  uploadsDir: process.env.UPLOADS_DIR || './uploads',
  maxFileSize: process.env.MAX_FILE_SIZE || 10 * 1024 * 1024,
};
