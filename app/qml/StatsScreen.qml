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
    property var viewModel: null

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
                cardLabel: qsTr("今日 OK")
                cardValue: String(ok)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.statusNG
                cardLabel: qsTr("今日 NG")
                cardValue: String(ng)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.accent
                cardLabel: qsTr("合格率")
                cardValue: okRate.toFixed(1) + "%"
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.statusWarning
                cardLabel: qsTr("总计")
                cardValue: String(total)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.textSecondary
                cardLabel: qsTr("过滤抑制")
                cardValue: String(total - ok - ng)
                cardSubtext: qsTr("误报已拦截")
                Layout.fillWidth: true
            }
        }

        // Defect distribution
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingSM

            Text {
                text: qsTr("缺陷分布")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeMD
                font.bold: true
            }

            RowLayout {
                spacing: Theme.spacingSM
                Text {
                    text: {
                        var dist = statsScreen.viewModel ? statsScreen.viewModel.defectDistribution : ({});
                        var keys = Object.keys(dist);
                        return keys.length === 0 ? qsTr("今日暂无缺陷") : keys.length + qsTr(" 种缺陷类型");
                    }
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSM
                }
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: {
                    var dist = statsScreen.viewModel ? statsScreen.viewModel.defectDistribution : ({});
                    return Object.keys(dist).length > 0
                        ? Object.entries(dist).map(function(e) { return { type: e[0], count: e[1] }; })
                        : [];
                }

                delegate: RowLayout {
                    width: ListView.view.width
                    height: 28
                    spacing: Theme.spacingMD

                    Rectangle {
                        Layout.preferredWidth: 12; Layout.preferredHeight: 12; radius: 6
                        color: Theme.statusNG
                    }
                    Text {
                        text: modelData.type
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        Layout.fillWidth: true
                    }
                    Text {
                        text: String(modelData.count)
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: true
                    }
                }
            }
        }
    }
}
