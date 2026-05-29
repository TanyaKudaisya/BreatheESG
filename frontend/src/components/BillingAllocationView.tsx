/**
 * Billing period allocation breakdown view.
 * Requirements: 20.4
 */

import {
  Table, TableBody, TableCell, TableHead, TableRow,
  Typography, Box,
} from '@mui/material';
import type { EmissionRecord } from '../types';

const MONTH_NAMES = [
  '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

interface Props {
  record: EmissionRecord;
}

export default function BillingAllocationView({ record }: Props) {
  const allocations = record.monthly_allocations;

  if (!allocations || allocations.length === 0) {
    return null;
  }

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>Monthly Billing Allocation</Typography>
      {record.billing_period_start && record.billing_period_end && (
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Original period: {record.billing_period_start} → {record.billing_period_end}
        </Typography>
      )}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Month</TableCell>
            <TableCell align="right">Allocated (kWh)</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {allocations.map((a) => (
            <TableRow key={`${a.year}-${a.month}`}>
              <TableCell>{MONTH_NAMES[a.month]} {a.year}</TableCell>
              <TableCell align="right">{Number(a.allocated_quantity).toFixed(2)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
