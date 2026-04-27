const { app, BrowserWindow, nativeImage } = require("electron");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const ROOT_DIR = path.resolve(__dirname, "..");
const ASSET_DIR = path.join(ROOT_DIR, "desktop", "assets");
const SOURCE_PNG_PATH = path.join(ASSET_DIR, "icon.png");
const APP_PNG_PATH = path.join(ASSET_DIR, "app-icon.png");
const ICO_PATH = path.join(ASSET_DIR, "icon.ico");
const ICNS_PATH = path.join(ASSET_DIR, "icon.icns");
const ICONSET_DIR = path.join(ASSET_DIR, "icon.iconset");

function ensureCleanDirectory(dirPath) {
  fs.rmSync(dirPath, { recursive: true, force: true });
  fs.mkdirSync(dirPath, { recursive: true });
}

function encodeIco(images) {
  const headerSize = 6;
  const directoryEntrySize = 16;
  const directorySize = images.length * directoryEntrySize;
  let offset = headerSize + directorySize;
  const chunks = [];
  const header = Buffer.alloc(headerSize);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);

  const entries = images.map(({ size, pngBuffer }) => {
    const entry = Buffer.alloc(directoryEntrySize);
    entry.writeUInt8(size >= 256 ? 0 : size, 0);
    entry.writeUInt8(size >= 256 ? 0 : size, 1);
    entry.writeUInt8(0, 2);
    entry.writeUInt8(0, 3);
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(pngBuffer.length, 8);
    entry.writeUInt32LE(offset, 12);
    offset += pngBuffer.length;
    chunks.push(pngBuffer);
    return entry;
  });

  return Buffer.concat([header, ...entries, ...chunks]);
}

async function buildMaskedAppIcon() {
  const sourceDataUrl = `data:image/png;base64,${fs.readFileSync(SOURCE_PNG_PATH, "base64")}`;
  const window = new BrowserWindow({
    width: 1024,
    height: 1024,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    webPreferences: {
      contextIsolation: true,
      sandbox: false,
    },
  });

  const html = `<!doctype html>
  <html>
    <head>
      <meta charset="utf-8" />
      <style>
        html, body {
          margin: 0;
          width: 100%;
          height: 100%;
          background: transparent;
          overflow: hidden;
        }
        canvas {
          width: 1024px;
          height: 1024px;
          display: block;
        }
      </style>
    </head>
    <body>
      <canvas id="icon" width="1024" height="1024"></canvas>
      <script>
        function roundedRect(ctx, x, y, width, height, radius) {
          ctx.beginPath();
          ctx.moveTo(x + radius, y);
          ctx.lineTo(x + width - radius, y);
          ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
          ctx.lineTo(x + width, y + height - radius);
          ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
          ctx.lineTo(x + radius, y + height);
          ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
          ctx.lineTo(x, y + radius);
          ctx.quadraticCurveTo(x, y, x + radius, y);
          ctx.closePath();
        }

        const canvas = document.getElementById("icon");
        const ctx = canvas.getContext("2d");
        const image = new Image();
        image.src = ${JSON.stringify(sourceDataUrl)};
        image.onload = () => {
          const probe = document.createElement("canvas");
          probe.width = image.width;
          probe.height = image.height;
          const probeCtx = probe.getContext("2d");
          probeCtx.drawImage(image, 0, 0);
          const { data, width, height } = probeCtx.getImageData(0, 0, image.width, image.height);

          let minX = width;
          let minY = height;
          let maxX = -1;
          let maxY = -1;

          for (let y = 0; y < height; y += 1) {
            for (let x = 0; x < width; x += 1) {
              const index = (y * width + x) * 4;
              const r = data[index];
              const g = data[index + 1];
              const b = data[index + 2];
              if (r < 248 || g < 248 || b < 248) {
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x);
                maxY = Math.max(maxY, y);
              }
            }
          }

          const cropPad = 4;
          const cropX = Math.max(0, minX - cropPad);
          const cropY = Math.max(0, minY - cropPad);
          const cropWidth = Math.min(width - cropX, maxX - minX + 1 + cropPad * 2);
          const cropHeight = Math.min(height - cropY, maxY - minY + 1 + cropPad * 2);

          ctx.clearRect(0, 0, 1024, 1024);
          roundedRect(ctx, 0, 0, 1024, 1024, 144);
          ctx.clip();
          ctx.drawImage(image, cropX, cropY, cropWidth, cropHeight, 0, 0, 1024, 1024);

          const imageData = ctx.getImageData(0, 0, 1024, 1024);
          const pixels = imageData.data;
          for (let index = 0; index < pixels.length; index += 4) {
            const red = pixels[index];
            const green = pixels[index + 1];
            const blue = pixels[index + 2];
            if (red > 244 && green > 244 && blue > 244) {
              pixels[index + 3] = 0;
            }
          }
          ctx.putImageData(imageData, 0, 0);
          window.__ICON_READY__ = true;
        };
        image.onerror = () => {
          window.__ICON_ERROR__ = "Failed to load source icon image.";
        };
      </script>
    </body>
  </html>`;

  await window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);

  const startedAt = Date.now();
  while (Date.now() - startedAt < 5000) {
    const state = await window.webContents.executeJavaScript(
      "({ ready: !!window.__ICON_READY__, error: window.__ICON_ERROR__ || null })",
      true,
    );
    if (state.error) {
      throw new Error(state.error);
    }
    if (state.ready) {
      const captured = await window.webContents.capturePage({
        x: 0,
        y: 0,
        width: 1024,
        height: 1024,
      });
      window.destroy();
      return captured.resize({ width: 1024, height: 1024, quality: "best" });
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  window.destroy();
  throw new Error("Timed out while generating the masked app icon.");
}

async function buildIcons() {
  if (!fs.existsSync(SOURCE_PNG_PATH)) {
    throw new Error(`Missing source icon: ${SOURCE_PNG_PATH}`);
  }

  const sourceIcon = nativeImage.createFromPath(SOURCE_PNG_PATH);
  if (sourceIcon.isEmpty()) {
    throw new Error(`Unable to read source icon: ${SOURCE_PNG_PATH}`);
  }

  const icon = await buildMaskedAppIcon();
  fs.writeFileSync(APP_PNG_PATH, icon.toPNG());

  ensureCleanDirectory(ICONSET_DIR);
  const icnsSizes = [16, 32, 128, 256, 512];
  for (const size of icnsSizes) {
    const iconAtSize = icon.resize({ width: size, height: size, quality: "best" });
    const iconAt2x = icon.resize({ width: size * 2, height: size * 2, quality: "best" });
    fs.writeFileSync(path.join(ICONSET_DIR, `icon_${size}x${size}.png`), iconAtSize.toPNG());
    fs.writeFileSync(path.join(ICONSET_DIR, `icon_${size}x${size}@2x.png`), iconAt2x.toPNG());
  }

  execFileSync("iconutil", ["-c", "icns", ICONSET_DIR, "-o", ICNS_PATH], { stdio: "inherit" });

  const icoSizes = [16, 32, 48, 64, 128, 256];
  const icoImages = icoSizes.map((size) => ({
    size,
    pngBuffer: icon.resize({ width: size, height: size, quality: "best" }).toPNG(),
  }));
  fs.writeFileSync(ICO_PATH, encodeIco(icoImages));
}

app.whenReady()
  .then(buildIcons)
  .then(() => app.quit())
  .catch((error) => {
    console.error(error);
    app.exit(1);
  });
