/**
 * File upload page.
 */

import { Box, Typography } from '@mui/material';
import FileUpload from '../components/FileUpload';

export default function UploadPage() {
  return (
    <Box>
      <Typography variant="h5" gutterBottom>Upload Data Files</Typography>
      <FileUpload />
    </Box>
  );
}
