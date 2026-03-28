import fs from 'fs';
import path from 'path';

const filePath = path.join(process.cwd(), 'prefix.json');

//  default create
if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify({ prefix: '.' }));
}

export const getPrefix = () => {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    return data.prefix;
};

export const setPrefix = (newPrefix) => {
    fs.writeFileSync(filePath, JSON.stringify({ prefix: newPrefix }, null, 2));
    return true;
};
