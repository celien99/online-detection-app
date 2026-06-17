import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
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

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("生产统计")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
                Layout.fillWidth: true
            }
            ActionButton {
                buttonText: qsTr("刷新")
                bgColor: Theme.bgTertiary
                implicitHeight: 36
                Layout.preferredWidth: 92
                onClicked: {
                    if (statsScreen.viewModel) statsScreen.viewModel.refresh()
                }
            }
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
                id: defectList
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: count > 0
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
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        Layout.preferredWidth: 180
                        Layout.preferredHeight: 8
                        radius: 4
                        color: Theme.bgTertiary
                        clip: true

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: parent.width * Math.min(1, modelData.count / Math.max(statsScreen.ng, 1))
                            radius: 4
                            color: Theme.statusNG
                        }
                    }
                    Text {
                        text: String(modelData.count)
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: true
                        Layout.preferredWidth: 56
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }

            EmptyState {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: defectList.count === 0
                title: qsTr("今日暂无缺陷记录")
                message: qsTr("缺陷分布会在 NG 记录产生后自动更新。")
                badgeText: qsTr("OK")
                accentColor: Theme.statusOK
            }
        }
    }
}
