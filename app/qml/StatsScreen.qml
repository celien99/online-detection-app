import QtQuick
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: statsScreen
    color: Theme.bgPrimary

    property int total: 0
    property int ok: 0
    property int ng: 0
    property real okRate: 0.0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingLG

        Text {
            text: qsTr("Statistics")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLG
            font.bold: true
        }

        // KPI cards
        RowLayout {
            spacing: Theme.spacingMD

            InfoCard {
                accentColor: Theme.statusOK
                cardLabel: qsTr("OK Today")
                cardValue: String(ok)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.statusNG
                cardLabel: qsTr("NG Today")
                cardValue: String(ng)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.accent
                cardLabel: qsTr("OK Rate")
                cardValue: okRate.toFixed(1) + "%"
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.statusWarning
                cardLabel: qsTr("Total")
                cardValue: String(total)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.textSecondary
                cardLabel: qsTr("Filter Suppressed")
                cardValue: String(total - ok - ng)
                cardSubtext: qsTr("false positive blocked")
                Layout.fillWidth: true
            }
        }

        // Placeholder for charts
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgCard
            radius: Theme.radiusMD
            border { width: 1; color: Theme.borderDefault }

            Column {
                anchors.centerIn: parent
                spacing: Theme.spacingSM
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("Trend Charts & Defect Distribution")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeMD
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("Charts will be available in a future update")
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeSM
                }
            }
        }
    }
}
