import QtQuick
import QtQuick.Layouts
import styles

Rectangle {
    id: root

    width: 440
    anchors.centerIn: parent
    visible: false
    z: 998
    radius: 14
    color: "#1a1e26"
    border { width: 1; color: Qt.rgba(1, 1, 1, 0.1) }

    property string title: ""
    property string acceptText: qsTr("确认")
    property string cancelText: qsTr("取消")
    property bool showCancel: true
    default property alias dialogContent: contentSlot.data

    signal accepted()
    signal rejected()

    function open() {
        root.visible = true;
        root.opacity = 0;
        fadeIn.start();
    }
    function close() {
        fadeOut.start();
    }

    OpacityAnimator {
        id: fadeIn
        target: root
        from: 0; to: 1
        duration: Theme.animFast
        easing.type: Easing.OutCubic
    }
    OpacityAnimator {
        id: fadeOut
        target: root
        from: 1; to: 0
        duration: Theme.animFast
        onStopped: { root.visible = false; root.opacity = 1; }
    }

    // Card inner highlight
    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.04) }
            GradientStop { position: 0.6; color: "transparent" }
        }
    }

    // Top accent bar
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 3
        radius: 14
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.accent }
            GradientStop { position: 1.0; color: Qt.rgba(0.345, 0.651, 1, 0.5) }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 3
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            Layout.leftMargin: 20
            Layout.rightMargin: 20

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: root.title
                color: Theme.textPrimary
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            color: Qt.rgba(1, 1, 1, 0.06)
        }

        Item {
            id: contentSlot
            Layout.fillWidth: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            Layout.topMargin: 14
            Layout.bottomMargin: 14
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            color: Qt.rgba(1, 1, 1, 0.06)
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: 20
            Layout.rightMargin: 14

            RowLayout {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Rectangle {
                    visible: root.showCancel
                    implicitWidth: 88
                    implicitHeight: 34
                    radius: 6
                    color: cancelMouse.containsMouse
                           ? Qt.rgba(1, 1, 1, 0.08)
                           : "transparent"
                    border { width: 1; color: Qt.rgba(1, 1, 1, 0.15) }

                    Behavior on color { ColorAnimation { duration: Theme.animFast } }

                    Text {
                        anchors.centerIn: parent
                        text: root.cancelText
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                    }

                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.rejected(); root.close(); }
                    }
                }

                Rectangle {
                    implicitWidth: 88
                    implicitHeight: 34
                    radius: 6
                    color: acceptMouse.containsMouse
                           ? "#4169e1"
                           : Theme.accent

                    Behavior on color { ColorAnimation { duration: Theme.animFast } }

                    Text {
                        anchors.centerIn: parent
                        text: root.acceptText
                        color: "#ffffff"
                        font.pixelSize: Theme.fontSizeSM
                        font.weight: Font.DemiBold
                    }

                    MouseArea {
                        id: acceptMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.accepted(); root.close(); }
                    }
                }
            }
        }
    }
}
