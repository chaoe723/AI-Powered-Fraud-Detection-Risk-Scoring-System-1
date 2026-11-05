import { render, screen } from '@testing-library/react'
import { RiskBadge } from './RiskBadge'

test.each([
  ['low', 'Thấp'],
  ['medium', 'Trung bình'],
  ['high', 'Cao'],
  ['critical', 'Nghiêm trọng'],
])('RiskBadge hiển thị nhãn tiếng Việt cho %s', (level, label) => {
  render(<RiskBadge level={level} />)
  expect(screen.getByText(label)).toBeInTheDocument()
})

test('RiskBadge không crash với giá trị lạ từ BE (bỏ qua field lạ)', () => {
  render(<RiskBadge level="future_level" />)
  expect(screen.getByText('future_level')).toBeInTheDocument()
})

test('RiskBadge hiển thị — khi thiếu dữ liệu', () => {
  render(<RiskBadge level={null} />)
  expect(screen.getByText('—')).toBeInTheDocument()
})
