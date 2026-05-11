/**
 * Database Path Resolution
 *
 * Determines where the SQLite session database lives on disk. Supports three
 * scenarios: explicit env override, packaged app (Electron userData), and
 * development mode (project-local .local/ directory). Includes a one-time
 * migration path from the legacy userData location to the workspace path so
 * that developers switching from an older build retain their conversation history.
 */
const fs = require("node:fs");
const path = require("node:path");

/** Development-mode default: keeps the DB inside the project for easy access/backup. */
function defaultDesktopDbPath(projectRootPath) {
  return path.join(projectRootPath, ".local", "assistant.db");
}

/** Original location used by early builds — stored in Electron's per-user app data. */
function legacyDesktopDbPath(userDataPath) {
  return path.join(userDataPath, "assistant.db");
}

/**
 * Resolves the final database path using the following priority:
 * 1. Explicit HYBRID_AI_DB_PATH env var (always wins)
 * 2. Packaged builds: use Electron userData (stable across installs)
 * 3. Dev builds: prefer project-local .local/assistant.db
 *    - If neither location exists yet, use the workspace path (fresh start)
 *    - If legacy exists but workspace does not, migrate legacy -> workspace
 *    - If migration fails, fall back to the legacy path gracefully
 */
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

/**
 * Copies the SQLite database (and WAL/SHM companions if present) from the
 * legacy userData location to the new workspace path. This preserves existing
 * sessions for developers who previously ran an older version of the app.
 */
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
