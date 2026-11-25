import { useState } from "react";
import { Form, Input, Modal, Typography, message } from "antd";
import { api, clearToken, errorText } from "../api";
import { useI18n } from "../i18n";
import { useMe } from "../me";

export function ChangePasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const me = useMe();
  const { t } = useI18n();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const path =
        me?.role === "partner" ? "/partner/v1/auth/password" : "/admin/v1/auth/password";
      await api(path, {
        method: "POST",
        body: JSON.stringify({
          old_password: values.old_password,
          new_password: values.new_password,
        }),
      });
      clearToken();
      message.success(
        t("Password updated. Please sign in with your new password.", "密码已修改，请用新密码重新登录")
      );
      window.location.href = "/login";
    } catch (e) {
      message.error(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={t("Change Password", "修改密码")}
      okText={t("Save & Sign In Again", "保存并重新登录")}
      cancelText={t("Cancel", "取消")}
      onCancel={() => {
        form.resetFields();
        onClose();
      }}
      onOk={submit}
      confirmLoading={saving}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          label={t("Current Password", "原密码")}
          name="old_password"
          rules={[{ required: true, message: t("Please enter current password", "请输入原密码") }]}
        >
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Form.Item
          label={t("New Password", "新密码")}
          name="new_password"
          rules={[
            { required: true, message: t("Please enter new password", "请输入新密码") },
            { min: 8, message: t("Must be at least 8 characters", "新密码至少 8 位") },
          ]}
        >
          <Input.Password
            autoComplete="new-password"
            placeholder={t("At least 8 characters", "至少 8 位")}
          />
        </Form.Item>
        <Form.Item
          label={t("Confirm New Password", "确认新密码")}
          name="confirm"
          dependencies={["new_password"]}
          rules={[
            { required: true, message: t("Please confirm new password", "请再次输入新密码") },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("new_password") === value) return Promise.resolve();
                return Promise.reject(
                  new Error(t("Passwords do not match", "两次输入不一致"))
                );
              },
            }),
          ]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
      </Form>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {t(
          "After updating, all active sessions for this account will be revoked immediately.",
          "修改成功后，该账号所有已登录会话立即失效，需要用新密码重新登录。"
        )}
      </Typography.Text>
    </Modal>
  );
}
