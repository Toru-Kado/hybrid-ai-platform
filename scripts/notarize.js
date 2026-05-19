const { notarize } = require('@electron/notarize');

exports.default = async function notarizing(context) {
  const { electronPlatformName, appOutDir } = context;
  if (electronPlatformName !== 'darwin') {
    return;
  }

  const appName = context.packager.appInfo.productFilename;
  const appPath = `${appOutDir}/${appName}.app`;

  console.log(`Notarizing ${appName}...`);

  try {
    await notarize({
      appBundleId: 'com.torukado.hybridai',
      appPath: appPath,
      appleId: process.env.APPLE_ID,
      appleIdPassword: process.env.APPLE_ID_PASSWORD,
      teamId: process.env.APPLE_TEAM_ID,
    });

    console.log(`Successfully notarized ${appName}!`);
  } catch (error) {
    console.error(`Notarization failed for ${appName}:`, error);
    // Don't fail the build if notarization fails
    // throw error;
  }
};