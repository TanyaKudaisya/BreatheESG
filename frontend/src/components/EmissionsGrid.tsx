/**
 * Task 16.1 – Paginated emissions data grid with filters, flag badges,
 * and bulk-selection checkboxes.
 */

import { useState } from 'react';
import {
  Box,
  Checkbox,
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
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import FlagIcon from '@mui/icons-material/Flag';
import { useEmissions } from '../hooks/useEmissions';
import type { EmissionRecord, EmissionRecordFilters } from '../types';
import { ApprovalStatus, Severity, SourceSystem } from '../types';

interface EmissionsGridProps {
  onRowClick?: (record: EmissionRecord) => void;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50];

function approvalColor(
  status: ApprovalStatus,
): 'default' | 'success' | 'error' | 'warning' {
  switch (status) {
    case ApprovalStatus.APPROVED:
      return 'success';
    case ApprovalStatus.REJECTED:
      return 'error';
    default:
      return 'warning';
  }
}

export default function EmissionsGrid({ onRowClick }: EmissionsGridProps) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Filters
  const [sourceSystem, setSourceSystem] = useState<SourceSystem | ''>('');
  const [scope, setScope] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const filters: EmissionRecordFilters = {
    page: page + 1,
    page_size: pageSize,
    ...(sourceSystem ? { source_system: sourceSystem } : {}),
    ...(scope ? { scope: Number(scope) } : {}),
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
  };

  const { data, isLoading, isError } = useEmissions(filters);
  const rows = data?.results ?? [];
  const total = data?.count ?? 0;

  // ── Selection helpers ──────────────────────────────────────────────────────
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const someSelected = rows.some((r) => selected.has(r.id)) && !allSelected;

  function toggleAll() {
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        rows.forEach((r) => next.delete(r.id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        rows.forEach((r) => next.add(r.id));
        return next;
      });
    }
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Reset page when filters change
  function handleFilterChange(fn: () => void) {
    fn();
    setPage(0);
  }

  return (
    <Box>
      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <Stack direction="row" spacing={2} flexWrap="wrap" mb={2}>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Source System</InputLabel>
          <Select
            label="Source System"
            value={sourceSystem}
            onChange={(e) =>
              handleFilterChange(() =>
                setSourceSystem(e.target.value as SourceSystem | ''),
              )
            }
          >
            <MenuItem value="">All</MenuItem>
            {Object.values(SourceSystem).map((s) => (
              <MenuItem key={s} value={s}>
                {s}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel>Scope</InputLabel>
          <Select
            label="Scope"
            value={scope}
            onChange={(e) =>
              handleFilterChange(() => setScope(e.target.value as string))
            }
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
          </Select>
        </FormControl>

        <TextField
          label="Date from"
          type="date"
          size="small"
          InputLabelProps={{ shrink: true }}
          value={dateFrom}
          onChange={(e) =>
            handleFilterChange(() => setDateFrom(e.target.value))
          }
        />

        <TextField
          label="Date to"
          type="date"
          size="small"
          InputLabelProps={{ shrink: true }}
          value={dateTo}
          onChange={(e) => handleFilterChange(() => setDateTo(e.target.value))}
        />

        {selected.size > 0 && (
          <Typography variant="body2" alignSelf="center" color="primary">
            {selected.size} selected
          </Typography>
        )}
      </Stack>

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="emissions table">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  indeterminate={someSelected}
                  checked={allSelected}
                  onChange={toggleAll}
                  inputProps={{ 'aria-label': 'select all rows' }}
                />
              </TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Source</TableCell>
              <TableCell>Location</TableCell>
              <TableCell>Fuel Type</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell>Unit</TableCell>
              <TableCell>Scope</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Flags</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={10} align="center">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {isError && (
              <TableRow>
                <TableCell colSpan={10} align="center" sx={{ color: 'error.main' }}>
                  Failed to load records.
                </TableCell>
              </TableRow>
            )}
            {!isLoading && !isError && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={10} align="center">
                  No records found.
                </TableCell>
              </TableRow>
            )}
            {rows.map((row) => {
              const flagCount = row.data_quality_flags?.length ?? 0;
              const hasError = row.data_quality_flags?.some(
                (f) => f.severity === Severity.ERROR,
              );
              return (
                <TableRow
                  key={row.id}
                  hover
                  selected={selected.has(row.id)}
                  onClick={() => onRowClick?.(row)}
                  sx={{ cursor: onRowClick ? 'pointer' : 'default' }}
                >
                  <TableCell
                    padding="checkbox"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleRow(row.id);
                    }}
                  >
                    <Checkbox
                      checked={selected.has(row.id)}
                      inputProps={{ 'aria-label': `select row ${row.id}` }}
                    />
                  </TableCell>
                  <TableCell>{row.transaction_date}</TableCell>
                  <TableCell>{row.source_system}</TableCell>
                  <TableCell>{row.location}</TableCell>
                  <TableCell>{row.fuel_type ?? '—'}</TableCell>
                  <TableCell align="right">
                    {row.normalized_quantity ?? row.original_quantity ?? '—'}
                  </TableCell>
                  <TableCell>
                    {row.normalized_unit ?? row.original_unit ?? '—'}
                  </TableCell>
                  <TableCell>
                    {row.scope != null
                      ? `Scope ${row.scope}${row.scope_category ? ` Cat ${row.scope_category}` : ''}`
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={row.approval_status}
                      size="small"
                      color={approvalColor(row.approval_status)}
                    />
                  </TableCell>
                  <TableCell>
                    {flagCount > 0 && (
                      <Tooltip
                        title={`${flagCount} flag${flagCount > 1 ? 's' : ''}`}
                      >
                        <Chip
                          icon={<FlagIcon fontSize="small" />}
                          label={flagCount}
                          size="small"
                          color={hasError ? 'error' : 'warning'}
                        />
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={total}
        page={page}
        rowsPerPage={pageSize}
        rowsPerPageOptions={PAGE_SIZE_OPTIONS}
        onPageChange={(_, newPage) => setPage(newPage)}
        onRowsPerPageChange={(e) => {
          setPageSize(Number(e.target.value));
          setPage(0);
        }}
      />
    </Box>
  );
}
