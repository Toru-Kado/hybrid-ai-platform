const fs = require("node:fs");
const path = require("node:path");

function defaultDesktopDbPath(projectRootPath) {
  return path.join(projectRootPath, ".local", "assistant.db");
}

function legacyDesktopDbPath(userDataPath) {
  return path.join(userDataPath, "assistant.db");
}

function resolveDesktopDbPath({
  envDbPath,
  isPackaged,
  projectRootPath,
  userDataPath,
  fsModule = fs,
}) {
  if (envDbPath) {
    return envDbPath;
  }

  const packagedPath = legacyDesktopDbPath(userDataPath);
  if (isPackaged) {
    return packagedPath;
  }

  const workspacePath = defaultDesktopDbPath(projectRootPath);
  if (fsModule.existsSync(workspacePath)) {
    return workspacePath;
  }

  if (!fsModule.existsSync(packagedPath)) {
    return workspacePath;
  }

  try {
    migrateLegacyDesktopDatabase({
      sourcePath: packagedPath,
      destinationPath: workspacePath,
      fsModule,
    });
    return workspacePath;
  } catch (_error) {
    return packagedPath;
  }
}

function migrateLegacyDesktopDatabase({
  sourcePath,
  destinationPath,
  fsModule = fs,
}) {
  fsModule.mkdirSync(path.dirname(destinationPath), { recursive: true });

  for (const suffix of ["", "-shm", "-wal"]) {
    const sourceFile = `${sourcePath}${suffix}`;
    if (!fsModule.existsSync(sourceFile)) {
      continue;
    }
    fsModule.copyFileSync(sourceFile, `${destinationPath}${suffix}`);
  }
}

module.exports = {
  defaultDesktopDbPath,
  legacyDesktopDbPath,
  migrateLegacyDesktopDatabase,
  resolveDesktopDbPath,
};
