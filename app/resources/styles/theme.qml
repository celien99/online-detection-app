pragma Singleton
import QtQuick

QtObject {
    readonly property color bgPrimary: "#1a1a2e"
    readonly property color bgSecondary: "#16213e"
    readonly property color bgTertiary: "#0f3460"
    readonly property color bgCard: "#1a1a2e"

    readonly property color statusOK: "#00ff88"
    readonly property color statusNG: "#ff4444"
    readonly property color statusWarning: "#ffaa00"
    readonly property color statusReject: "#ff8800"

    readonly property color accent: "#4488ff"

    readonly property color textPrimary: "#ffffff"
    readonly property color textSecondary: "#888888"
    readonly property color textMuted: "#666666"

    readonly property int fontSizeXL: 24
    readonly property int fontSizeLG: 18
    readonly property int fontSizeMD: 14
    readonly property int fontSizeSM: 11
    readonly property int fontSizeXS: 9

    readonly property int touchMin: 48
}
