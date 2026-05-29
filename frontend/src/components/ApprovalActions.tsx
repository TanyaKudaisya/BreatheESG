/**
 * Task 18.1 – Approve / Reject buttons with Snackbar notifications.
 * Approve is disabled when the record has unresolved ERROR flags.
 */

import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Snackbar,
  Stack,
  TextField,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { useApproveEmission, useRejectEmission } from '../hooks/useEmissions';
import type { EmissionRecord } from '../types';
import { ApprovalStatus, Severity } from '../types';

interface ApprovalActionsProps {
  record: EmissionRecord;
  onDone?: () => void;
}

export default function ApprovalActions({ record, onDone }: ApprovalActionsProps) {
  const [showRejectField, setShowRejectField] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  const approveMutation = useApproveEmission();
  const rejectMutation = useRejectEmission();

  const hasErrorFlags = record.data_quality_flags?.some(
    (f) => f.severity === Severity.ERROR && !f.is_resolved,
  );

  const isLocked = record.is_locked;
  const isApproved = record.approval_status === ApprovalStatus.APPROVED;
  const isRejected = record.approval_status === ApprovalStatus.REJECTED;

  function handleApprove() {
    approveMutation.mutate(record.id, {
      onSuccess: () => {
        setSnackbar({ open: true, message: 'Record approved.', severity: 'success' });
        onDone?.();
      },
      onError: () => {
        setSnackbar({
          open: true,
          message: 'Approval failed. Please try again.',
          severity: 'error',
        });
      },
    });
  }

  function handleReject() {
    if (!rejectReason.trim()) return;
    rejectMutation.mutate(
      { id: record.id, reason: rejectReason },
      {
        onSuccess: () => {
          setSnackbar({ open: true, message: 'Record rejected.', severity: 'success' });
          setShowRejectField(false);
          setRejectReason('');
          onDone?.();
        },
        onError: () => {
          setSnackbar({
            open: true,
            message: 'Rejection failed. Please try again.',
            severity: 'error',
          });
        },
      },
    );
  }

  if (isLocked) {
    return (
      <Box>
        <Alert severity="info" sx={{ py: 0.5 }}>
          Record is locked and cannot be approved or rejected.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      {showRejectField ? (
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <TextField
            label="Rejection reason"
            size="small"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            sx={{ flexGrow: 1 }}
            autoFocus
            multiline
            minRows={1}
          />
          <Button
            variant="contained"
            color="error"
            startIcon={<CancelIcon />}
            onClick={handleReject}
            disabled={!rejectReason.trim() || rejectMutation.isPending}
          >
            {rejectMutation.isPending ? 'Rejecting…' : 'Confirm'}
          </Button>
          <Button onClick={() => setShowRejectField(false)}>Cancel</Button>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1}>
          {!isApproved && (
            <Button
              variant="contained"
              color="success"
              startIcon={<CheckCircleIcon />}
              onClick={handleApprove}
              disabled={hasErrorFlags || approveMutation.isPending}
              title={
                hasErrorFlags
                  ? 'Resolve all ERROR-level flags before approving'
                  : undefined
              }
            >
              {approveMutation.isPending ? 'Approving…' : 'Approve'}
            </Button>
          )}
          {!isRejected && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<CancelIcon />}
              onClick={() => setShowRejectField(true)}
            >
              Reject
            </Button>
          )}
        </Stack>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
