import axios from 'axios';

export default async (sock, msg, args, extra) => {
    const chat = msg.key.remoteJid;
    const url = args.join(' ');
    
    if (!url) {
        return await sock.sendMessage(chat, {
            text: `❌ Provide Spotify URL\n\nUsage: *.spotify* <spotify_url>\n\nExamples:\n.spotify https://open.spotify.com/track/0JGTfiC4Z41GEEpMYLbWwO\n.spotify https://open.spotify.com/track/ABC123`
        }, { quoted: msg });
    }
    
    if (!url.includes('spotify.com')) {
        return await sock.sendMessage(chat, {
            text: '❌ Invalid Spotify URL. Must be from spotify.com'
        }, { quoted: msg });
    }
    
    await sock.sendMessage(chat, { react: { text: '🎵', key: msg.key } });
    
    try {
        const apiUrl = `https://api.sparky.biz.id/api/httpsy?url=${encodeURIComponent(url)}`;
        const response = await axios.get(apiUrl, { timeout: 15000 });
        
        if (!response.data.status || !response.data.data) {
            return await sock.sendMessage(chat, {
                text: '❌ Failed to fetch song info. The track may be:\n• Private\n• Deleted\n• Not available in your region'
            }, { quoted: msg });
        }
        
        const data = response.data.data;
        const title = data.title || 'Unknown Title';
        const artist = data.artist || 'Unknown Artist';
        const cover = data.cover;
        const downloadUrl = data.download;
        
        const info = `🎵 *SPOTIFY TRACK*\n\n📌 *Title:* ${title}\n🎤 *Artist:* ${artist}`;
        
        if (cover) {
            await sock.sendMessage(chat, {
                image: { url: cover },
                caption: info
            }, { quoted: msg });
        } else {
            await sock.sendMessage(chat, { text: info }, { quoted: msg });
        }
        
        if (downloadUrl) {
            await sock.sendMessage(chat, {
                text: `📥 *DOWNLOAD LINK*\n\n${downloadUrl}`
            }, { quoted: msg });
        }
        
    } catch (e) {
        console.error('Spotify Downloader Error:', e.message);
        await sock.sendMessage(chat, {
            text: '❌ Download failed.\n\nPossible reasons:\n• Invalid URL\n• Track not found\n• Server is down\n\nTry again later!'
        }, { quoted: msg });
    }
};
