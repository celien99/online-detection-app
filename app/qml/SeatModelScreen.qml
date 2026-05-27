import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: seatModelScreen
    color: Theme.bgPrimary

    property var viewModel: null

    ToastNotification {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        z: 100
    }

    Connections {
        target: seatModelScreen.viewModel
        function onToast(message, level) { toast.show(message, level); }
        function onRequestConfirmSwitch(modelId) { confirmDialog.modelId = modelId; confirmDialog.open(); }
    }

    Dialog {
        id: confirmDialog
        property string modelId: ""
        title: qsTr("切换座椅型号")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        width: 400
        contentItem: Text {
            text: qsTr("切换型号将重新加载检测引擎，确认继续？")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSM
            wrapMode: Text.Wrap
        }
        onAccepted: {
            if (seatModelScreen.viewModel && confirmDialog.modelId) {
                seatModelScreen.viewModel.confirmSwitch(confirmDialog.modelId);
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("座椅型号管理")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentGreenDim
                implicitWidth: addBtnText.implicitWidth + 24
                implicitHeight: 36
                Text {
                    id: addBtnText
                    anchors.centerIn: parent
                    text: qsTr("+ 新增型号")
                    color: Theme.accentGreen
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: addDialog.open()
                }
            }
        }

        ListView {
            id: modelList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: seatModelScreen.viewModel ? seatModelScreen.viewModel.seatModels : []
            spacing: Theme.spacingSM

            delegate: Rectangle {
                width: ListView.view.width
                implicitHeight: 80
                color: Theme.cardGlass
                radius: Theme.radiusMD
                border { width: 1; color: modelData.is_default ? Theme.accentGreen : Theme.cardGlassBorder }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingMD

                    Rectangle {
                        width: 10; height: 10; radius: 5
                        color: modelData.is_default ? Theme.accentGreen : Theme.textMuted
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.display_name || modelData.id
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                        Text {
                            text: modelData.description || ""
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                            visible: text !== ""
                        }
                        Text {
                            text: qsTr("关联相机: ") + (modelData.camera_ids ? modelData.camera_ids.join(", ") : qsTr("无"))
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingXS
                        Rectangle {
                            radius: Theme.radiusSM
                            color: Theme.bgTertiary
                            implicitWidth: 48; implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("编辑")
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    editDialog.modelId = modelData.id;
                                    editDialog.nameField = modelData.display_name || "";
                                    editDialog.descField = modelData.description || "";
                                    editDialog.open();
                                }
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: modelData.is_default ? Theme.bgTertiary : Theme.accentGreenDim
                            implicitWidth: modelData.is_default ? 48 : 72
                            implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: modelData.is_default ? qsTr("默认") : qsTr("设为默认")
                                color: modelData.is_default ? Theme.textMuted : Theme.accentGreen
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !modelData.is_default
                                onClicked: seatModelScreen.viewModel.setActive(modelData.id)
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: Qt.rgba(0.973, 0.318, 0.286, 0.1)
                            implicitWidth: 40; implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("删除")
                                color: Theme.statusNG
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: seatModelScreen.viewModel.deleteModel(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: addDialog
        title: qsTr("新增座椅型号")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        width: 420
        padding: Theme.spacingLG

        background: Rectangle {
            color: Theme.bgSecondary
            radius: Theme.radiusLG
            border { width: 1; color: Theme.borderStrong }
        }

        header: Text {
            text: qsTr("新增座椅型号")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
            padding: Theme.spacingMD
        }

        ColumnLayout {
            spacing: Theme.spacingMD
            Layout.fillWidth: true

            Text {
                text: qsTr("型号 ID:")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: Theme.cardGlassBorder }
                TextInput {
                    id: addIdField
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                }
            }

            Text {
                text: qsTr("显示名称:")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: Theme.cardGlassBorder }
                TextInput {
                    id: addNameField
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                }
            }

            Text {
                text: qsTr("描述:")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: Theme.cardGlassBorder }
                TextInput {
                    id: addDescField
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                }
            }

            Item { height: Theme.spacingSM; width: 1 }
        }
        onAccepted: {
            seatModelScreen.viewModel.createModel(addIdField.text, addNameField.text, addDescField.text);
        }
        onOpened: {
            addIdField.text = "";
            addNameField.text = "";
            addDescField.text = "";
            addIdField.forceActiveFocus();
        }
    }

    Dialog {
        id: editDialog
        property string modelId: ""
        property string nameField: ""
        property string descField: ""
        title: qsTr("编辑型号")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        width: 420
        padding: Theme.spacingLG

        background: Rectangle {
            color: Theme.bgSecondary
            radius: Theme.radiusLG
            border { width: 1; color: Theme.borderStrong }
        }

        header: Text {
            text: qsTr("编辑型号")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
            padding: Theme.spacingMD
        }

        ColumnLayout {
            spacing: Theme.spacingMD
            Layout.fillWidth: true

            Text {
                text: qsTr("显示名称:")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: Theme.cardGlassBorder }
                TextInput {
                    id: editNameField
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                }
            }

            Text {
                text: qsTr("描述:")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: Theme.cardGlassBorder }
                TextInput {
                    id: editDescField
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                }
            }

            Item { height: Theme.spacingSM; width: 1 }
        }
        onAccepted: {
            seatModelScreen.viewModel.updateModel(editDialog.modelId, editNameField.text, editDescField.text);
        }
        onOpened: {
            editNameField.text = editDialog.nameField;
            editDescField.text = editDialog.descField;
            editNameField.forceActiveFocus();
        }
    }
}
