import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MessagesOverTimeChart from './MessagesOverTimeChart';
import { messagesAPI } from '../utils/api';

jest.mock('../utils/api', () => ({
  messagesAPI: {
    getMessagesOverTime: jest.fn(),
  },
}));

const series = [
  { date: '2026-08-01', count: 4 },
  { date: '2026-08-02', count: 6 },
  { date: '2026-08-03', count: 2 },
  { date: '2026-08-04', count: 8 },
  { date: '2026-08-05', count: 1 },
];

function toYmd(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

beforeAll(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

beforeEach(() => {
  messagesAPI.getMessagesOverTime.mockResolvedValue({ success: true, data: series });
});

test('muestra presets de producción y no aplica el calendario hasta tener inicio y fin', async () => {
  const onDateRangeChange = jest.fn();
  render(
    <MessagesOverTimeChart
      filters={{ channel: ['abc'] }}
      onDateRangeChange={onDateRangeChange}
      selectedDateStart=""
      selectedDateEnd=""
    />
  );

  await waitFor(() => {
    expect(screen.getByText(/Evolución de mensajes/i)).toBeInTheDocument();
  });

  expect(screen.getByRole('button', { name: 'Última semana' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Último mes' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Último año' })).toBeInTheDocument();

  expect(messagesAPI.getMessagesOverTime).toHaveBeenCalledWith({ channel: ['abc'] });
  expect(onDateRangeChange).not.toHaveBeenCalled();

  const input = screen.getByLabelText('Rango de fechas');
  await userEvent.click(input);

  await waitFor(() => {
    expect(document.querySelector('.react-datepicker')).toBeTruthy();
  });
  expect(document.querySelectorAll('.react-datepicker__month-container').length).toBe(2);

  const enabledDays = Array.from(
    document.querySelectorAll('.react-datepicker__day:not(.react-datepicker__day--disabled):not(.react-datepicker__day--outside-month)')
  );
  expect(enabledDays.length).toBeGreaterThan(1);

  fireEvent.click(enabledDays[0]);
  expect(onDateRangeChange).not.toHaveBeenCalled();
  expect(document.querySelector('.react-datepicker')).toBeTruthy();

  fireEvent.click(enabledDays[Math.min(3, enabledDays.length - 1)]);
  await waitFor(() => {
    expect(onDateRangeChange).toHaveBeenCalledTimes(1);
  });
  const [start, end] = onDateRangeChange.mock.calls[0];
  expect(start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(end).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(start <= end).toBe(true);
});

test('los presets aplican un rango completo de una vez', async () => {
  const onDateRangeChange = jest.fn();
  render(
    <MessagesOverTimeChart
      filters={{}}
      onDateRangeChange={onDateRangeChange}
      selectedDateStart=""
      selectedDateEnd=""
    />
  );

  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Última semana' })).toBeInTheDocument();
  });

  await userEvent.click(screen.getByRole('button', { name: 'Última semana' }));

  const end = toYmd(new Date());
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 6);
  const start = toYmd(startDate);
  expect(onDateRangeChange).toHaveBeenCalledWith(start, end);
});

test('no vuelve a pedir la serie cuando solo cambian las fechas', async () => {
  const onDateRangeChange = jest.fn();
  const { rerender } = render(
    <MessagesOverTimeChart
      filters={{ dateStart: '', dateEnd: '' }}
      onDateRangeChange={onDateRangeChange}
      selectedDateStart=""
      selectedDateEnd=""
    />
  );

  await waitFor(() => {
    expect(messagesAPI.getMessagesOverTime).toHaveBeenCalledTimes(1);
  });

  rerender(
    <MessagesOverTimeChart
      filters={{ dateStart: '2026-08-02', dateEnd: '2026-08-04' }}
      onDateRangeChange={onDateRangeChange}
      selectedDateStart="2026-08-02"
      selectedDateEnd="2026-08-04"
    />
  );

  await waitFor(() => {
    expect(screen.getByText(/mensajes entre/i)).toBeInTheDocument();
  });
  expect(messagesAPI.getMessagesOverTime).toHaveBeenCalledTimes(1);
  expect(screen.queryByText(/Cargando gráfico de evolución/i)).not.toBeInTheDocument();
});

test('limpiar el filtro restaura el título inicial del gráfico', async () => {
  const onDateRangeChange = jest.fn();
  const { rerender } = render(
    <MessagesOverTimeChart
      filters={{}}
      onDateRangeChange={onDateRangeChange}
      selectedDateStart="2026-08-02"
      selectedDateEnd="2026-08-04"
    />
  );

  await waitFor(() => {
    expect(screen.getByText(/mensajes entre/i)).toBeInTheDocument();
    expect(screen.getByTestId('chart-brush')).toHaveAttribute('data-start-index', '1');
    expect(screen.getByTestId('chart-brush')).toHaveAttribute('data-end-index', '3');
  });

  await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtro de fecha' }));
  expect(onDateRangeChange).toHaveBeenCalledWith('', '');
  expect(screen.getByLabelText('Rango de fechas')).toHaveValue('');
  expect(screen.getByTestId('chart-brush')).toHaveAttribute('data-start-index', '0');
  expect(screen.getByTestId('chart-brush')).toHaveAttribute('data-end-index', '4');

  rerender(
    <MessagesOverTimeChart
      filters={{}}
      onDateRangeChange={onDateRangeChange}
      selectedDateStart=""
      selectedDateEnd=""
    />
  );

  await waitFor(() => {
    expect(screen.getByText(/Evolución de mensajes/i)).toBeInTheDocument();
  });
  expect(screen.queryByRole('button', { name: 'Limpiar filtro de fecha' })).not.toBeInTheDocument();
  expect(screen.getByTestId('chart-brush')).toHaveAttribute('data-start-index', '0');
  expect(screen.getByTestId('chart-brush')).toHaveAttribute('data-end-index', '4');
});
