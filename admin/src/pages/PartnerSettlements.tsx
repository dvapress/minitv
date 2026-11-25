import { Space, Table, Tag, Typography } from "antd";
import { formatTime, useLoad } from "../hooks";
import { useI18n } from "../i18n";

type SettlementRow = {
  id: number;
  month: string;
  currency: string;
  gross_cents: number;
  revenue_cents: number;
  effective_share_bps: number;
  order_count: number;
  status: string;
  confirmed_at: string | null;
  paid_at: string | null;
};

const money = (cents: number, currency = "USD") =>
  `${currency === "USD" ? "$" : ""}${(cents / 100).toFixed(2)}`;

export default function PartnerSettlements() {
  const { t } = useI18n();
  const { data, loading } = useLoad<{ items: SettlementRow[] }>("/partner/v1/settlements", {
    items: [],
  });

  const statusMeta: Record<string, { text: string; color?: string }> = {
    draft: { text: t("Pending", "待确认"), color: "orange" },
    confirmed: { text: t("Confirmed", "已确认"), color: "blue" },
    paid: { text: t("Paid", "已打款"), color: "green" },
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      <Typography.Text type="secondary">
        {t(
          "Settled monthly with statements issued the following month; share rate is based on the effective rate at payment time.",
          "自然月结算，次月出对账单；分成按每笔订单支付时生效的比例计算。"
        )}
      </Typography.Text>
      <Table<SettlementRow>
        rowKey="id"
        loading={loading}
        dataSource={data.items}
        pagination={false}
        columns={[
          { title: t("Month", "月份"), dataIndex: "month", width: 110 },
          {
            title: t("Gross Amount", "首单金额"),
            dataIndex: "gross_cents",
            width: 120,
            render: (value: number, row) => money(value, row.currency),
          },
          {
            title: t("Share Rate", "分成比例"),
            dataIndex: "effective_share_bps",
            width: 100,
            render: (value: number) => `${(value / 100).toFixed(2)}%`,
          },
          {
            title: t("Payout", "应结金额"),
            dataIndex: "revenue_cents",
            width: 120,
            render: (value: number, row) => (
              <Typography.Text strong>{money(value, row.currency)}</Typography.Text>
            ),
          },
          { title: t("Orders", "订单数"), dataIndex: "order_count", width: 80 },
          {
            title: t("Status", "状态"),
            dataIndex: "status",
            width: 100,
            render: (value: string) => {
              const meta = statusMeta[value] ?? { text: value };
              return <Tag color={meta.color}>{meta.text}</Tag>;
            },
          },
          {
            title: t("Confirmed / Paid", "确认 / 打款"),
            key: "dates",
            width: 200,
            render: (_, row) => (
              <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>
                {formatTime(row.confirmed_at)} / {formatTime(row.paid_at)}
              </span>
            ),
          },
        ]}
      />
    </Space>
  );
}
