import QtQuick
import "components"

Rectangle {
    id: statsScreen
    color: Theme.bgPrimary

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
                cardValue: "—"
                width: 160
            }
            InfoCard {
                accentColor: Theme.statusNG
                cardLabel: qsTr("今日 NG")
                cardValue: "—"
                width: 160
            }
            InfoCard {
                accentColor: Theme.accent
                cardLabel: qsTr("OK 率")
                cardValue: "—"
                width: 160
            }
            InfoCard {
                accentColor: Theme.statusWarning
                cardLabel: qsTr("Filter 抑制")
                cardValue: "—"
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
