const { Menu, shell, app } = require("electron");

function buildAppMenu(mainWindow) {
  const isMac = process.platform === "darwin";
  const isDev = !app.isPackaged;

  function sendMenuAction(action) {
    mainWindow.webContents.send("menu:action", action);
  }

  const template = [
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: "about" },
              { type: "separator" },
              { role: "services" },
              { type: "separator" },
              { role: "hide" },
              { role: "hideOthers" },
              { role: "unhide" },
              { type: "separator" },
              { role: "quit" },
            ],
          },
        ]
      : []),

    {
      label: "File",
      submenu: [
        {
          label: "New Session",
          accelerator: "CmdOrCtrl+N",
          click: () => sendMenuAction("new-session"),
        },
        {
          label: "Export Transcript",
          accelerator: "CmdOrCtrl+Shift+E",
          click: () => sendMenuAction("export-transcript"),
        },
        { type: "separator" },
        isMac ? { role: "close" } : { role: "quit" },
      ],
    },

    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },

    {
      label: "View",
      submenu: [
        {
          label: "Toggle Sidebar",
          accelerator: "CmdOrCtrl+\\",
          click: () => sendMenuAction("toggle-sidebar"),
        },
        { type: "separator" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { role: "resetZoom" },
        { type: "separator" },
        { role: "togglefullscreen" },
        ...(isDev
          ? [
              { type: "separator" },
              { role: "toggleDevTools" },
              { role: "reload" },
              { role: "forceReload" },
            ]
          : []),
      ],
    },

    {
      label: "Help",
      submenu: [
        {
          label: "Documentation",
          click: () =>
            shell.openExternal("https://github.com/Toru-Kado/hybrid-ai-platform#readme"),
        },
        {
          label: "Report Issue",
          click: () =>
            shell.openExternal("https://github.com/Toru-Kado/hybrid-ai-platform/issues/new"),
        },
        ...(isMac
          ? []
          : [{ type: "separator" }, { role: "about" }]),
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

module.exports = { buildAppMenu };
