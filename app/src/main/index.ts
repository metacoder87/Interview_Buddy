import { electronApp, is, optimizer } from '@electron-toolkit/utils'
import { app, BrowserWindow, globalShortcut, nativeImage, screen, session, shell } from 'electron'
import { join } from 'path'
import icon from '../../resources/icon.png?asset'
import { cleanupIpcHandlers, initializeIpcHandlers } from './ipc/handlers'
import { coreLink } from './services/coreLink'

let mainWindow: BrowserWindow | null = null
let isSessionActive = false

function createWindow(): void {
  const appIcon = nativeImage.createFromPath(icon)

  // Calculate dynamic initial height based on laptop screen work area (approx 75% height)
  const primaryDisplay = screen.getPrimaryDisplay()
  const { height: workAreaHeight } = primaryDisplay.workAreaSize
  const initialHeight = Math.max(550, Math.min(700, Math.floor(workAreaHeight * 0.95)))

  // Create the browser window with screen share protection
  mainWindow = new BrowserWindow({
    width: 620,
    height: initialHeight,
    minWidth: 380,
    minHeight: 500,
    show: false,
    autoHideMenuBar: true,
    frame: false, // Frameless for custom title bar
    transparent: true, // text-only overlay: only rendered text is visible
    backgroundColor: '#00000000',
    alwaysOnTop: true, // Stay on top by default
    skipTaskbar: true, // stealth: no taskbar / Alt-Tab presence
    resizable: false,
    icon: appIcon,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // Enable screen share protection - hides window from screen capture
  mainWindow.setContentProtection(true)

  mainWindow.on('ready-to-show', () => {
    if (process.platform === 'win32' && !appIcon.isEmpty()) {
      mainWindow?.setIcon(appIcon)
    }
    mainWindow?.show()
    // Never steal focus — overlay must stay invisible during the interview
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // Initialize IPC handlers
  initializeIpcHandlers(mainWindow)

  // Grant microphone permissions
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    const allowedPermissions = ['media', 'mediaKeySystem', 'audioCapture']
    if (allowedPermissions.includes(permission)) {
      callback(true)
    } else {
      callback(false)
    }
  })

  // HMR for renderer base on electron-vite cli.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// This method will be called when Electron has finished initialization
app.whenReady().then(() => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.interview-copilot')

  // Default open or close DevTools by F12 in development
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  createWindow()

  // Register global hotkeys (none steal focus)
  globalShortcut.register('CommandOrControl+Alt+Space', () => {
    isSessionActive = !isSessionActive
    coreLink.send({ t: isSessionActive ? 'start' : 'stop' })
    console.log(`[hotkey] session ${isSessionActive ? 'started' : 'stopped'}`)
  })

  globalShortcut.register('CommandOrControl+Alt+Q', () => {
    coreLink.send({ t: 'trigger' })
    console.log('[hotkey] force-answer triggered')
  })

  globalShortcut.register('CommandOrControl+Alt+H', () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide()
    } else {
      mainWindow?.show()
    }
  })

  globalShortcut.register('CommandOrControl+Alt+C', () => {
    mainWindow?.webContents.send('clear-answer')
    console.log('[hotkey] clear answer')
  })

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', () => {
  cleanupIpcHandlers()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Cleanup on quit
app.on('before-quit', () => {
  cleanupIpcHandlers()
  globalShortcut.unregisterAll()
})
