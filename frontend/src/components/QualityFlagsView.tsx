/**
 * Task 17.1 – Table of data quality flags with filter by flag_type
 * and a resolve action per row.
 */

import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useQualityFlags, useResolveFlag } from '../hooks/useQualityFlags';
import { FlagType, Severity } from '../types';

const PAGE_SIZE = 25;

export default function QualityFlagsView() {
  const [flagType, setFlagType] = useState<FlagType | ''>('');
  const [showResolved, setShowResolved] = useState(false);
  const [page, setPage] = useState(0);

  const { data, isLoading, isError } = useQualityFlags({
    flag_type: flagType || undefined,
    is_resolved: showResolved ? undefined : false,
    page: page + 1,
    page_size: PAGE_SIZE,
  });

  const resolveMutation = useResolveFlag();

  const rows = data?.results ?? [];
  const total = data?.count ?? 0;

  return (
    <Box>
      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <Stack direction="row" spacing={2} mb={2} flexWrap="wrap" alignItems="center">
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Flag Type</InputLabel>
          <Select
            label="Flag Type"
            value={flagType}
            onChange={(e) => {
              setFlagType(e.target.value as FlagType | '');
              setPage(0);
            }}
          >
            <MenuItem value="">All types</MenuItem>
            {Object.values(FlagType).map((ft) => (
              <MenuItem key={ft} value={ft}>
                {ft.replace(/_/g, ' ')}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Button
          size="small"
          variant={showResolved ? 'contained' : 'outlined'}
          onClick={() => {
            setShowResolved((v) => !v);
            setPage(0);
          }}
        >
          {showResolved ? 'Showing all' : 'Show resolved'}
        </Button>

        <Typography variant="body2" color="text.secondary">
          {total} flag{total !== 1 ? 's' : ''}
        </Typography>
      </Stack>

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="quality flags table">
          <TableHead>
            <TableRow>
              <TableCell>Flag Type</TableCell>
              <TableCell>Severity</TableCell>
              <TableCell>Message</TableCell>
              <TableCell>Field</TableCell>
              <TableCell>Record ID</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Action</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {isError && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ color: 'error.main' }}>
                  Failed to load flags.
                </TableCell>
              </TableRow>
            )}
            {!isLoading && !isError && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No flags found.
                </TableCell>
              </TableRow>
            )}
            {rows.map((flag) => (
              <TableRow key={flag.id}>
                <TableCell>
                  <Chip
                    label={flag.flag_type.replace(/_/g, ' ')}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={flag.severity}
                    size="small"
                    color={flag.severity === Severity.ERROR ? 'error' : 'warning'}
                  />
                </TableCell>
                <TableCell sx={{ maxWidth: 300 }}>
                  <Typography variant="body2" noWrap title={flag.message}>
                    {flag.message}
                  </Typography>
                </TableCell>
                <TableCell>{flag.field_name ?? '—'}</TableCell>
                <TableCell>
                  <Typography
                    variant="body2"
                    fontFamily="monospace"
                    fontSize="0.75rem"
                  >
                    {flag.emission_record_id.slice(0, 8)}…
                  </Typography>
                </TableCell>
                <TableCell>
                  {flag.is_resolved ? (
                    <Chip label="Resolved" size="small" color="success" />
                  ) : (
                    <Chip label="Open" size="small" color="default" />
                  )}
                </TableCell>
                <TableCell>
                  {!flag.is_resolved && (
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => resolveMutation.mutate(flag.id)}
                      disabled={resolveMutation.isPending}
                    >
                      Resolve
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={total}
        page={page}
        rowsPerPage={PAGE_SIZE}
        rowsPerPageOptions={[PAGE_SIZE]}
        onPageChange={(_, newPage) => setPage(newPage)}
      />
    </Box>
  );
}
