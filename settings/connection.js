import fs from 'fs' 
import { DisconnectReason } from '@whiskeysockets/baileys'
import qrcode from 'qrcode-terminal'

const connection = async (sock, startNexa, saveCreds) => {
    
    // Creds update ivide thanne handle cheyyunnathaanu nallathu
    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update

        // --- QR GENERATOR ---
        if (qr && !process.argv.includes('--pairing-code')) {
            console.log('\x1b[33m--- SCAN THE QR CODE BELOW ---\x1b[0m');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const reason = lastDisconnect?.error?.output?.statusCode
            console.log("❌ Connection Closed. Reason Code:", reason)

            // 401 (Unauthorized) or 405 (Logged Out) aanel session delete cheyyendi varum
            if (reason === DisconnectReason.loggedOut || reason === 401 || reason === 405) {
                console.log("❌ Session Expired or Logged Out. Please delete session folder and scan again.")
                process.exit()
            } 
            else if (reason === DisconnectReason.restartRequired || reason === DisconnectReason.connectionLost) {
                console.log("🔁 Reconnecting...")
                startNexa()
            } 
            else {
                // Mattu errors aanenkil 5 second kazhinju reconnect cheyyaam
                console.log("⚠️ Unknown error, trying to reconnect in 5s...")
                setTimeout(() => startNexa(), 5000)
            }
        }

        else if (connection === 'open') {
            console.log('\x1b[36m✅ Nexa-Bot MD CONNECTED SUCCESSFULLY!\x1b[0m')
            
            // Login Message Logic
            const myNumber = sock.user.id.split(':')[0] + "@s.whatsapp.net"
            const activeMsg = `
            ╭━━〔 *Nexa-Bot-MD* 〕━━╮
            ┃🛠️ STATUS: Online
            ┃👤 OWNER: Arun & Ansad
            ╰━━━━━━━━━━━━━━━╯`

            try {
                const imagePath = './media/nexa.jpg'
                if (fs.existsSync(imagePath)) {
                    await sock.sendMessage(myNumber, { 
                        image: fs.readFileSync(imagePath), 
                        caption: activeMsg 
                    })
                } else {
                    await sock.sendMessage(myNumber, { text: activeMsg })
                }
            } catch (err) {
                console.log("❌ Login Notification Error:", err.message)
            }
        }
    })
}

export default connection
