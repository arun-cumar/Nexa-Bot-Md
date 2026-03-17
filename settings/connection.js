import fs from 'fs'
import { DisconnectReason } from '@whiskeysockets/baileys'
 const connection = async (sock, startNexa, saveCreds) => {
 sock.ev.on('connection.update', async (update) => {
 const { connection, lastDisconnect } = update
if(connection === 'close'){
const reason = lastDisconnect?.error?.output?.statusCode
console.log("❌ Connection Closed :", reason)

if(reason === DisconnectReason.badSession){
console.log("Bad Session File, Delete Session")
process.exit()
}

else if(reason === DisconnectReason.connectionClosed){
console.log("🔁 Connection closed, reconnecting...")
startNexa()
}

else if(reason === DisconnectReason.connectionLost){
console.log("⚠️ Connection Lost, reconnecting...")
startNexa()
}

else if(reason === DisconnectReason.connectionReplaced){
console.log("⚠️ Connection Replaced")
process.exit()
}

else if(reason === DisconnectReason.loggedOut){
console.log("❌ Logged Out Delete Session")
process.exit()
}

else if(reason === DisconnectReason.restartRequired){
console.log("🔄 Restart Required")
startNexa()
}

else if(reason === DisconnectReason.timedOut){
console.log("⏱️ Connection TimedOut Reconnecting")
startNexa()
}

else{
sock.end(`Unknown DisconnectReason: ${reason}`)
}

}

       else if(connection === 'open'){

      console.log('\x1b[36m✅ Nexa-Bot MD CONNECTED SUCCESSFULLY!\x1b[0m')

     const myNumber = sock.user.id.split(':')[0] + "@s.whatsapp.net"

      const activeMsg = `
        ╭━━〔 *Nexa-Bot-MD* 〕━━╮
         ┃🛠️ STATUS: Online
          ┃👤 OWNER: Arun & Ansad 
           ┃⚙️ MODE: Public
          ┃📌 PREFIX: [ .,!#$@ ]
        ┃🤖 BOT CONNECTED SUCCESSFULLY
        ╰━━━━━━━━━━━━━━━╯

        *THE UNDERWORLD IS ACTIVE*
`

   try {

    const imagePath = './media/image.jpg'

   if(fs.existsSync(imagePath)){

     await sock.sendMessage(myNumber,{
    image: fs.readFileSync(imagePath),
      caption: activeMsg,

       contextInfo:{
      mentionedJid:[myNumber],
       isForwarded:true,
       forwardingScore:999,

     forwardedNewsletterMessageInfo:{
     newsletterJid:'120363422992896382@newsletter',
    newsletterName:'Nexa-Bot',
    serverMessageId:143
   },

      externalAdReply:{
      title:'Nexa-Bot ACTIVE',
      body:'Underworld WhatsApp Bot',
      thumbnail: fs.readFileSync(imagePath),
      sourceUrl:'https://whatsapp.com/channel/0029VbB59W9GehENxhoI5l24',
      mediaType:1,
      renderLargerThumbnail:true
       }

     }

  })

}

}catch(err){
console.log("❌ Error sending owner message",err)
       }

    }

  })

           sock.ev.on('creds.update', saveCreds)

          sock.ev.on('messages.upsert', async ({ messages }) => {

          const msg = messages[0]

           if(!msg.message) return

           const sender = msg.key.remoteJid

          console.log("📩 Message From :", sender)

      })

   }

export default connection
