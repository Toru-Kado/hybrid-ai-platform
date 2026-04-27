// @vitest-environment node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  resolveDesktopDbPath,
  defaultDesktopDbPath,
  legacyDesktopDbPath,
} = require("./db-path.cjs");

const tempDirs = [];

function makeTempDir() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "desktop-db-path-"));
  tempDirs.push(tempDir);
  return tempDir;
}

afterEach(() => {
  while (tempDirs.length > 0) {
    fs.rmSync(tempDirs.pop(), { recursive: true, force: true });
  }
});

describe("resolveDesktopDbPath", () => {
  it("uses the project-local database during development", () => {
    const rootDir = makeTempDir();
    const userDataDir = makeTempDir();

    const dbPath = resolveDesktopDbPath({
      envDbPath: "",
      isPackaged: false,
      projectRootPath: rootDir,
      userDataPath: userDataDir,
    });

    expect(dbPath).toBe(defaultDesktopDbPath(rootDir));
  });

  it("migrates an existing legacy development database into the project-local path", () => {
    const rootDir = makeTempDir();
    const userDataDir = makeTempDir();
    const legacyPath = legacyDesktopDbPath(userDataDir);
    const workspacePath = defaultDesktopDbPath(rootDir);

    fs.mkdirSync(path.dirname(legacyPath), { recursive: true });
    fs.writeFileSync(legacyPath, "legacy-db");
    fs.writeFileSync(`${legacyPath}-wal`, "legacy-wal");

    const dbPath = resolveDesktopDbPath({
      envDbPath: "",
      isPackaged: false,
      projectRootPath: rootDir,
      userDataPath: userDataDir,
    });

    expect(dbPath).toBe(workspacePath);
    expect(fs.readFileSync(workspacePath, "utf8")).toBe("legacy-db");
    expect(fs.readFileSync(`${workspacePath}-wal`, "utf8")).toBe("legacy-wal");
  });

  it("keeps using the packaged-user-data database in packaged builds", () => {
    const rootDir = makeTempDir();
    const userDataDir = makeTempDir();

    const dbPath = resolveDesktopDbPath({
      envDbPath: "",
      isPackaged: true,
      projectRootPath: rootDir,
      userDataPath: userDataDir,
    });

    expect(dbPath).toBe(legacyDesktopDbPath(userDataDir));
  });

  it("honors an explicit environment override", () => {
    const rootDir = makeTempDir();
    const userDataDir = makeTempDir();
    const overridePath = path.join(makeTempDir(), "custom.db");

    const dbPath = resolveDesktopDbPath({
      envDbPath: overridePath,
      isPackaged: false,
      projectRootPath: rootDir,
      userDataPath: userDataDir,
    });

    expect(dbPath).toBe(overridePath);
  });
});
