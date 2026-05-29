/**
 * Task 16.2 – Record detail modal with tabs: Details, Audit Trail, Quality Flags.
 * Edit form for quantity/unit/date/location (disabled when locked).
 * Approve / Reject buttons.
 */

import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import { useAuditTrail } from '../hooks/useAuditTrail';
import {
  useUpdateEmission,
  useApproveEmission,
  useRejectEmission,
} from '../hooks/useEmissions';
import type { EmissionRecord } from '../types';
import { ApprovalStatus, Severity } from '../types';

interface RecordDetailModalProps {
  record: EmissionRecord | null;
  open: boolean;
  onClose: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <Box role="tabpanel" hidden={value !== index} pt={2}>
      {value === index && children}
    </Box>
  );
}

export default function RecordDetailModal({
  record,
  open,
  onClose,
}: RecordDetailModalProps) {
  const [tab, setTab] = useState(0);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectField, setShowRejectField] = useState(false);

  // Edit form state
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('');
  const [date, setDate] = useState('');
  const [location, setLocation] = useState('');

  const { data: auditTrail, isLoading: auditLoading } = useAuditTrail(
    record?.id ?? '',
  );
  const updateMutation = useUpdateEmission();
  const approveMutation = useApproveEmission();
  const rejectMutation = useRejectEmission();

  if (!record) return null;

  const isLocked = record.is_locked;
  const hasErrorFlags = record.data_quality_flags?.some(
    (f) => f.severity === Severity.ERROR && !f.is_resolved,
  );

  function handleOpen() {
    // Pre-fill form with current values
    setQuantity(String(record!.original_quantity ?? ''));
    setUnit(record!.original_unit ?? '');
    setDate(record!.transaction_date ?? '');
    setLocation(record!.location ?? '');
    setTab(0);
    setShowRejectField(false);
    setRejectReason('');
  }

  function handleSave() {
    if (!record) return;
    updateMutation.mutate({
      id: record.id,
      payload: {
        original_quantity: quantity ? Number(quantity) : undefined,
        original_unit: unit || undefined,
        transaction_date: date || undefined,
        location: location || undefined,
      },
    });
  }

  function handleApprove() {
    if (!record) return;
    approveMutation.mutate(record.id, { onSuccess: onClose });
  }

  function handleReject() {
    if (!record || !rejectReason.trim()) return;
    rejectMutation.mutate(
      { id: record.id, reason: rejectReason },
      { onSuccess: onClose },
    );
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      TransitionProps={{ onEntered: handleOpen }}
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h6" component="span" sx={{ flexGrow: 1 }}>
            Emission Record
          </Typography>
          {isLocked && (
            <Chip
              icon={<LockIcon fontSize="small" />}
              label="Locked"
              size="small"
              color="default"
            />
          )}
          <Chip
            label={record.approval_status}
            size="small"
            color={
              record.approval_status === ApprovalStatus.APPROVED
                ? 'success'
                : record.approval_status === ApprovalStatus.REJECTED
                  ? 'error'
                  : 'warning'
            }
          />
        </Stack>
      </DialogTitle>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="Details" />
        <Tab label="Audit Trail" />
        <Tab label={`Quality Flags (${record.data_quality_flags?.length ?? 0})`} />
      </Tabs>

      <DialogContent>
        {/* ── Details tab ─────────────────────────────────────────────── */}
        <TabPanel value={tab} index={0}>
          <Stack spacing={2}>
            <Stack direction="row" spacing={2} flexWrap="wrap">
              <TextField
                label="Date"
                type="date"
                size="small"
                InputLabelProps={{ shrink: true }}
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={isLocked}
              />
              <TextField
                label="Location"
                size="small"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                disabled={isLocked}
              />
              <TextField
                label="Quantity"
                type="number"
                size="small"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                disabled={isLocked}
              />
              <TextField
                label="Unit"
                size="small"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                disabled={isLocked}
              />
            </Stack>

            <Divider />

            <Typography variant="subtitle2" color="text.secondary">
              Read-only fields
            </Typography>
            <Stack direction="row" spacing={4} flexWrap="wrap">
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Source
                </Typography>
                <Typography>{record.source_system}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Scope
                </Typography>
                <Typography>
                  {record.scope != null
                    ? `Scope ${record.scope}${record.scope_category ? ` Cat ${record.scope_category}` : ''}`
                    : '—'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Fuel Type
                </Typography>
                <Typography>{record.fuel_type ?? '—'}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Ingested
                </Typography>
                <Typography>
                  {new Date(record.ingestion_timestamp).toLocaleString()}
                </Typography>
              </Box>
            </Stack>

            {!isLocked && (
              <Box>
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving…' : 'Save changes'}
                </Button>
              </Box>
            )}
          </Stack>
        </TabPanel>

        {/* ── Audit Trail tab ─────────────────────────────────────────── */}
        <TabPanel value={tab} index={1}>
          {auditLoading ? (
            <CircularProgress size={24} />
          ) : !auditTrail || auditTrail.length === 0 ? (
            <Typography color="text.secondary">No audit events yet.</Typography>
          ) : (
            <Stack spacing={1}>
              {auditTrail.map((event) => (
                <Box
                  key={event.id}
                  p={1.5}
                  border={1}
                  borderColor="divider"
                  borderRadius={1}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip label={event.event_type} size="small" />
                    <Typography variant="body2" color="text.secondary">
                      {new Date(event.timestamp).toLocaleString()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      by {event.user_id}
                    </Typography>
                  </Stack>
                  {event.field_name && (
                    <Typography variant="body2" mt={0.5}>
                      <strong>{event.field_name}</strong>:{' '}
                      <span style={{ textDecoration: 'line-through' }}>
                        {event.old_value ?? '—'}
                      </span>{' '}
                      → {event.new_value ?? '—'}
                    </Typography>
                  )}
                </Box>
              ))}
            </Stack>
          )}
        </TabPanel>

        {/* ── Quality Flags tab ───────────────────────────────────────── */}
        <TabPanel value={tab} index={2}>
          {!record.data_quality_flags || record.data_quality_flags.length === 0 ? (
            <Typography color="text.secondary">No quality flags.</Typography>
          ) : (
            <Stack spacing={1}>
              {record.data_quality_flags.map((flag) => (
                <Box
                  key={flag.id}
                  p={1.5}
                  border={1}
                  borderColor={
                    flag.severity === Severity.ERROR ? 'error.main' : 'warning.main'
                  }
                  borderRadius={1}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip
                      label={flag.severity}
                      size="small"
                      color={flag.severity === Severity.ERROR ? 'error' : 'warning'}
                    />
                    <Chip label={flag.flag_type} size="small" variant="outlined" />
                    {flag.is_resolved && (
                      <Chip label="Resolved" size="small" color="success" />
                    )}
                  </Stack>
                  <Typography variant="body2" mt={0.5}>
                    {flag.message}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </TabPanel>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        {showRejectField ? (
          <Stack direction="row" spacing={1} sx={{ flexGrow: 1 }}>
            <TextField
              label="Rejection reason"
              size="small"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              sx={{ flexGrow: 1 }}
              autoFocus
            />
            <Button
              variant="contained"
              color="error"
              onClick={handleReject}
              disabled={!rejectReason.trim() || rejectMutation.isPending}
            >
              Confirm Reject
            </Button>
            <Button onClick={() => setShowRejectField(false)}>Cancel</Button>
          </Stack>
        ) : (
          <>
            <Button onClick={onClose}>Close</Button>
            {!isLocked &&
              record.approval_status !== ApprovalStatus.REJECTED && (
                <Button
                  color="error"
                  onClick={() => setShowRejectField(true)}
                >
                  Reject
                </Button>
              )}
            {!isLocked &&
              record.approval_status !== ApprovalStatus.APPROVED && (
                <Button
                  variant="contained"
                  color="success"
                  onClick={handleApprove}
                  disabled={hasErrorFlags || approveMutation.isPending}
                  title={
                    hasErrorFlags
                      ? 'Resolve ERROR flags before approving'
                      : undefined
                  }
                >
                  {approveMutation.isPending ? 'Approving…' : 'Approve'}
                </Button>
              )}
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
