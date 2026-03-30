export default {
    name: 'add',
    category: 'group',
    desc: 'Add a user to the group',
    async execute(sock, msg, { args, prefix, command }) {
        try {
          
            const isGroup = msg.key.remoteJid.endsWith('@g.us');
            if (!isGroup) return sock.sendMessage(msg.key.remoteJid, { text: 'This command can only be used in groups!' }, { quoted: msg });

          
            let text = args.join(' ');
            if (!text && !msg.message?.extendedTextMessage?.contextInfo?.participant) {
                return sock.sendMessage(msg.key.remoteJid, { text: `Usage: ${prefix + command} 91xxxxxxxx\nOr reply to a message.` }, { quoted: msg });
            }

            let users = text ? text.replace(/[^0-9]/g, '') : msg.message?.extendedTextMessage?.contextInfo?.participant.split('@')[0];
            
            if (!users) return sock.sendMessage(msg.key.remoteJid, { text: 'Invalid number!' }, { quoted: msg });

            let jid = users + '@s.whatsapp.net';

            const response = await sock.groupParticipantsUpdate(msg.key.remoteJid, [jid], 'add');

            // Handling response
            if (response[0].status === "200") {
                await sock.sendMessage(msg.key.remoteJid, { text: `Successfully added @${users} to the group.`, mentions: [jid] }, { quoted: msg });
            } else if (response[0].status === "403") {
                await sock.sendMessage(msg.key.remoteJid, { text: `Could not add @${users}. Their privacy settings might be blocking invites.`, mentions: [jid] }, { quoted: msg });
            } else {
                await sock.sendMessage(msg.key.remoteJid, { text: `Failed to add @${users}. Status: ${response[0].status}`, mentions: [jid] }, { quoted: msg });
            }

        } catch (e) {
            console.error('Add Command Error:', e);
            await sock.sendMessage(msg.key.remoteJid, { text: 'An error occurred while trying to add the user.' }, { quoted: msg });
        }
    }
};
