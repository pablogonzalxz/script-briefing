const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const app = express();
app.use(bodyParser.json());

app.post('/send-message', async (req, res) => {
    const {to, message } = req.body;

    if (!to || !message){
        return res.status(400).json({ error: 'require pararms to and message'});
    }
    try {
        await client.sendMessage(to, message);
        res.status(200).json({ status: 'message send'});
    } catch (err) {
        console.error('error send message', err);
        res.status(500).json({error: 'error send message'});
    }
});
const client = new Client({
    authStrategy: new LocalAuth(),
});

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('ready');
});

client.on('message', async msg => {
    try {
       console.log('Mensagem recebida:', msg.body || '[sem texto]');
        
        let messagePayload = {
            from: msg.from,
            type: msg.type,
        };

        if (msg.type === 'document') {
            const attachmentData = await msg.downloadMedia();
            const fileBuffer = Buffer.from(attachmentData.data, 'base64');

            let fileName = msg.body;

            if (!fileName) {
                const ext = getExtensionFromMimeType(msg.mimetype) || '.bin';
                fileName = `document_${Date.now()}${ext}`;
            } else {
                if (!path.extname(fileName)) {
                    const ext = getExtensionFromMimeType(msg.mimetype) || '';
                    fileName += ext;
                }
            }

            const uploadsDir = path.join(__dirname, 'uploads');
            if (!fs.existsSync(uploadsDir)) {
                fs.mkdirSync(uploadsDir, { recursive: true });
            }

            const filePath = path.join(uploadsDir, fileName);
            fs.writeFileSync(filePath, fileBuffer);

            messagePayload = {
                from: msg.from,
                type: "document",
                document: {
                    id: msg.id._serialized,
                    mime_type: msg.mimetype,
                    filename: fileName,
                    file_path: filePath,
                }
            };
        }
        const webhookPayload = {
            entry: [{
                changes: [{
                    value: {
                        messages: [messagePayload]
                    }
                }]
            }]
        };
        const response = await axios.post('http://localhost:5000/receive_webhook', webhookPayload);
    } catch (error) {
        console.error('error send backend:', error);
    }
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`server run in ${PORT}`);
});
client.initialize();
