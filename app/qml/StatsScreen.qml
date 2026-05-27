import QtQuick
import "components"

Rectangle {
    id: statsScreen
    color: Theme.bgPrimary

    property int total: 0
    property int ok: 0
    property int ng: 0
    property real okRate: 0.0

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        Text {
            text: qsTr("📊 统计报表")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLG
            font.bold: true
        }

        Row { spacing: 12
            InfoCard {
                accentColor: Theme.statusOK
                cardLabel: qsTr("今日 OK")
                cardValue: String(ok)
                width: 160
            }
            InfoCard {
                accentColor: Theme.statusNG
                cardLabel: qsTr("今日 NG")
                cardValue: String(ng)
                width: 160
            }
            InfoCard {
                accentColor: Theme.accent
                cardLabel: qsTr("OK 率")
                cardValue: okRate.toFixed(1) + "%"
                width: 160
            }
            InfoCard {
                accentColor: Theme.statusWarning
                cardLabel: qsTr("Filter 抑制")
                cardValue: String(total - ok - ng)
                cardSubtext: "Filter Suppressed"
                width: 160
            }
        }

        Text {
            text: qsTr("完整统计面板将在后续迭代中补充趋势图和缺陷分布图表")
            color: Theme.textMuted
            font.pixelSize: Theme.fontSizeSM
        }
    }
}
