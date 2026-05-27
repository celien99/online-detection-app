import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import styles

Rectangle {
    id: settingsScreen
    color: Theme.bgPrimary

    property int selectedIndex: 0

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Sidebar
        Rectangle {
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: Theme.bgSecondary

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0

                Text {
                    text: qsTr("Settings")
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMD
                    font.bold: true
                    Layout.margins: Theme.spacingMD
                }

                ListView {
                    id: navList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: [
                        qsTr("Camera Config"),
                        qsTr("Detection Models"),
                        qsTr("PLC Communication"),
                        qsTr("Offline Platform"),
                        qsTr("Alert Settings"),
                        qsTr("Storage"),
                        qsTr("About")
                    ]
                    currentIndex: settingsScreen.selectedIndex

                    delegate: Rectangle {
                        width: navList.width
                        height: 44
                        color: index === navList.currentIndex ? Theme.bgTertiary : "transparent"

                        Rectangle {
                            visible: index === navList.currentIndex
                            width: 3; height: parent.height
                            color: Theme.accent
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.spacingLG
                            text: modelData
                            color: index === navList.currentIndex ? Theme.textPrimary : Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: index === navList.currentIndex
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: settingsScreen.selectedIndex = index
                        }
                    }
                }
            }
        }

        // Content area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgPrimary

            Column {
                anchors.centerIn: parent
                spacing: Theme.spacingSM
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: {
                        var items = [
                            qsTr("Camera Configuration"),
                            qsTr("Detection Model Settings"),
                            qsTr("PLC Communication Settings"),
                            qsTr("Offline Platform Settings"),
                            qsTr("Alert Settings"),
                            qsTr("Storage Management"),
                            qsTr("About")
                        ];
                        return items[settingsScreen.selectedIndex] || "";
                    }
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMD
                    font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("Configuration forms will be available in a future update")
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeSM
                }
            }
        }
    }
}
