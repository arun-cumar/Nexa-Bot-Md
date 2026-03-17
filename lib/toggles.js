import fs from "fs";

const toggleFile = "./media/toggles.json";

export const getToggles = () => {
    if (fs.existsSync(toggleFile)) {
        return JSON.parse(fs.readFileSync(toggleFile));
    }
    return {};
};

export const saveToggles = (toggles) => {
    fs.writeFileSync(toggleFile, JSON.stringify(toggles, null, 2));
};
