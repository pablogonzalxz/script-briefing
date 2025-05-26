const express = require('express');
const router = express.Router();

function createMessageRoutes(whatsappService, messageProcessor) {
  router.post('/send-message', async (req, res) => {
    const { to, message } = req.body;

    if (!to || !message) {
      return res.status(400).json({ 
        error: 'Missing required parameters: to and message' 
      });
    }

    try {
      await whatsappService.sendMessage(to, message);
      res.status(200).json({ 
        status: 'success',
        message: 'Message sent successfully' 
      });
    } catch (error) {
      console.error('Error sending message:', error);
      res.status(500).json({ 
        error: 'Failed to send message',
        details: error.message 
      });
    }
  });

  router.get('/user-stats/:userId', async (req, res) => {
    const { userId } = req.params;

    try {
      const stats = await messageProcessor.getUserStats(userId);
      
      if (stats && stats.status === 'success') {
        res.status(200).json(stats);
      } else {
        res.status(404).json({ 
          error: 'User not found or error getting stats',
          details: stats?.message || 'Unknown error'
        });
      }
    } catch (error) {
      console.error('Error getting user stats:', error);
      res.status(500).json({ 
        error: 'Failed to get user stats',
        details: error.message 
      });
    }
  });

  router.get('/status', (req, res) => {
    res.json({
      status: whatsappService.isReady ? 'ready' : 'not_ready',
      timestamp: new Date().toISOString()
    });
  });

  return router;
}

module.exports = createMessageRoutes;