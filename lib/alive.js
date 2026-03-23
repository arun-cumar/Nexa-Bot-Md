
export const aliveStyles = (data) => {
    const { botName, owner, prefix, uptime, ram, platform } = data;

    const styles = [
        //  1
 `╭━━〔 *✅ ${botName} ONLINE* 〕━━╮
┃ 🤖 *Bot:* ${botName}
┃ 👤 *Owner:* ${owner}
┃ ⏱️ *Uptime:* ${uptime}
┃ 💾 *RAM:* ${ram}
╰━━━━━━━━━━━━━━━━━━━━╯`,

        // 2
 `✨ *${botName} IS ACTIVE* ✨
________________________       
● *Owner:* ${owner}
● *Prefix:* ${prefix}
● *Platform:* ${platform}
● *Uptime:* ${uptime}
_________________________`,

        // 3
 `🚀 [ ${botName} SYSTEM STATUS ] 🚀
        
» *STATUS:* ONLINE 🟢
» *OWNER:* ${owner}
» *MEMORY:* ${ram}
» *OS:* ${platform}
» *UPTIME:* ${uptime}`,

        // 4
`╔═══════════════╗
   🌟 ${botName} ALIVE 🌟
╠════════════════╣
   👤 Owner: ${owner}
   ⏳ Uptime: ${uptime}
   🛠 Platform: ${platform}
╚════════════════╝`
    ];

    return styles[Math.floor(Math.random() * styles.length)];
};
