import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts'

type ChartEntry = { date: string; price: number }

export default function PredictionHistoryChart({ data }: { data: ChartEntry[] }) {
  return <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid stroke="var(--line)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 13 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 13 }} tickFormatter={(value: number) => new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value)} width={50} /><Tooltip formatter={(value) => [new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(Number(value)), 'Estimate']} contentStyle={{ borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)', fontSize: 14 }} /><Line type="monotone" dataKey="price" stroke="var(--forest)" strokeWidth={2.5} dot={{ r: 4, fill: 'var(--accent)', strokeWidth: 0 }} activeDot={{ r: 6, fill: 'var(--forest)' }} /></LineChart></ResponsiveContainer></div>
}
