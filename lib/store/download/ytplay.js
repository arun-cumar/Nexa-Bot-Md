import axios from 'axios';

export async function ytPlay(query) {
    const apis = [
        `https://api-faa.my.id/faa/ytplay?query=${encodeURIComponent(query)}`,
        `https://api.giftedtech.my.id/api/search/ytplay?query=${encodeURIComponent(query)}`,
        `https://api.dreaded.site/api/youtube/play?query=${encodeURIComponent(query)}`
    ];

    for (let api of apis) {
        try {
            const res = await axios.get(api);
            const data = res.data;

            // Different API response formats
            if (data?.result) {
                return {
                    title: data.result.title,
                    audio: data.result.audio || data.result.audioUrl,
                    video: data.result.video || data.result.videoUrl,
                    thumbnail: data.result.thumbnail
                };
            }

            if (data?.data) {
                return {
                    title: data.data.title,
                    audio: data.data.audio,
                    video: data.data.video,
                    thumbnail: data.data.thumbnail
                };
            }

            if (data?.title && (data?.audio || data?.video)) {
                return {
                    title: data.title,
                    audio: data.audio,
                    video: data.video,
                    thumbnail: data.thumbnail
                };
            }

        } catch (e) {
            console.log("API Failed:", api);
        }
    }

    throw new Error("All APIs failed");
}
