// © 2026 arun•°Cumar. All Rights Reserved.
export const aliveStyles = (data) => {
    const { botName, owner, prefix, uptime, ram, platform } = data;

    const styles = [
`╭━〔 🌟 *${botName}* 🌟 〕━╮ 
┃ 👤 *Dev:* ${owner} 
┃ ⚡ *Status:* ONLINE 
┃ ⏳ *Up:* ${uptime} 
┃ 📟 *RAM:* ${ram} 
╰━━━━━━━━━━━━━━╯`,

`┏━━━━━━━━━━━━┓ 
🚀 *${botName} ENGINE* 
┗━━━━━━━━━━━━━┛ 
❏ *Owner:* ${owner}
❏ *Speed:* 25ms 
❏ *Uptime:* ${uptime} 
❏ *Memory:* ${ram}`,

`✨ SYSTEM STATUS ✨
🤖 Bot: ${botName}
👑 Admin: ${owner}
🔋 Power: ${uptime}
🧠 Brain: ${ram}
--------------------------`,

`〔 🔥 *${botName} CONNECTED* 🔥 〕
» *Creator:* ${owner} 
» *Platform:* ${platform} 
» *Runtime:* ${uptime} 
» *Usage:* ${ram}`,

`◈━◈━◈━ [*${botName}*] ━◈━◈━◈ 
👤 *Owner:* ${owner} 
⏱️ *Online:* ${uptime}
📟 *Server:* ${ram}
🛰️ *Ping:* 12ms
◈━◈━◈━◈━◈━◈━◈━◈━◈`,

`💠 *${botName} LIVE* 💠 
━━━━━━━━━━━━━━
● *Author:* ${owner} 
● *Uptime:* ${uptime}
● *RAM:* ${ram} 
● *Ver:* 4.0.1 
━━━━━━━━━━━━━━`,

`『 ⚡ *${botName} DASHBOARD* ⚡ 』
⚓ *Master:* ${owner} 
⏳ *Active:* ${uptime} 
💾 *Memory:* ${ram} 
🌐 *Mode:* Public`,

`╔══════════════╗ 
⭐ *${botName} IS READY*
╚══════════════╝
▸ *Owner:* ${owner}
▸ *Uptime:* ${uptime}
▸ *Ram:* ${ram}`,

`⚡ SYSTEM BOOTED ⚡
🤖 BOT: ${botName}
👑 BOSS: ${owner}
⏰ TIME: ${uptime}
🔋 RAM: ${ram}`,

`╭─ • [* ${botName} *] • ─╮
👤 *Owner:* ${owner} 
📟 *RAM:* ${ram} 
⏲️ *Up:* ${uptime} 
╰─ • ────────── • ─╯`,

`💎 *PREMIUM STATUS* 💎
┃ 🤖 Name: ${botName} 
┃ 👤 User: ${owner} 
┃ ⏱️ Live: ${uptime} 
┃ 📊 Data: ${ram}`,

`●─〔 *${botName}* 〕─●
» *Owner:* ${owner}
» *Prefix:* ${prefix} 
» *Memory:* ${ram} 
» *Uptime:* ${uptime} 
●─────────────●`,

`[ ❄️ ${botName} ONLINE ❄️ ]
✦ Owner: ${owner}
✦ Uptime: ${uptime}
✦ Memory: ${ram}
✦ Platform: ${platform}`,

`┍━━━━━━━━━━━┑ 
🟢 *${botName} STATUS* 
┕━━━━━━━━━━━━┙ 
📍 *Owner:* ${owner} 
📍 *Uptime:* ${uptime} 
📍 *RAM:* ${ram}`,

`🏮 *${botName} ACTIVE* 🏮
━━━━━━━━━━━━━━ 
◈ *Dev:* ${owner} 
◈ *Up:* ${uptime}
◈ *Ram:* ${ram} 
◈ *Cmd:* ${prefix}help`,

    
`╭━〔 ⚡ *BOT INFO* ⚡ 〕━╮ 
┃ 👤 *Dev:* ${owner}
┃ 🤖 *Bot:* ${botName} 
┃ ⏳ *Up:* ${uptime} 
┃ 📟 *RAM:* ${ram} 
╰━━━━━━━━━━━━━━━━╯`,

`✨ SYSTEM INFO: ${botName}
👑 King: ${owner}
⏱️ Stay: ${uptime}
💾 Storage: ${ram}
-----------------------`,

`🛡️ *${botName} GUARD* 🛡️ 
» *Admin:* ${owner}
» *Uptime:* ${uptime} 
» *Server:* ${ram} 
» *Status:* Active`,

`⚡ *${botName}IS RUNNING*
━━━━━━━━━━━━━━ 
👤 *Owner:* ${owner} 
📈 *Uptime:* ${uptime}
📉 *RAM:* ${ram}
📡 *Mode:* ${platform}`,

`╔═◈【 *${botName}* 】◈═╗ 
👤 *Owner:* ${owner} 
⏱️ *Uptime:* ${uptime} 
💾 *Memory:* ${ram} 
╚═◈═══════════◈═╝`,

    ];

    return styles[Math.floor(Math.random() * styles.length)];
};
