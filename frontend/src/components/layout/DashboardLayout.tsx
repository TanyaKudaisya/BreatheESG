/**
 * Main dashboard layout with navigation sidebar.
 * Detailed page components are implemented in tasks 16–20.
 */

import { useState } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  Button,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import TableChartIcon from '@mui/icons-material/TableChart';
import FlagIcon from '@mui/icons-material/Flag';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import SettingsIcon from '@mui/icons-material/Settings';
import { useCurrentUser, useLogout } from '../../hooks/useAuth';
import EmissionsPage from '../../pages/EmissionsPage';
import QualityFlagsPage from '../../pages/QualityFlagsPage';
import UploadPage from '../../pages/UploadPage';

const DRAWER_WIDTH = 240;

const navItems = [
  { label: 'Emissions', path: '/', icon: <TableChartIcon /> },
  { label: 'Data Quality', path: '/quality', icon: <FlagIcon /> },
  { label: 'Approvals', path: '/approvals', icon: <CheckCircleIcon /> },
  { label: 'Upload', path: '/upload', icon: <UploadFileIcon /> },
  { label: 'Config', path: '/config', icon: <SettingsIcon /> },
];

function Placeholder({ title }: { title: string }) {
  return (
    <Box p={4}>
      <Typography variant="h4">{title}</Typography>
      <Typography color="text.secondary" mt={1}>
        This view will be implemented in a subsequent task.
      </Typography>
    </Box>
  );
}

export default function DashboardLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  const drawer = (
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap>
          Breathe ESG
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {navItems.map((item) => (
          <ListItem key={item.path} disablePadding>
            <ListItemButton
              component={Link}
              to={item.path}
              selected={location.pathname === item.path}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setMobileOpen(!mobileOpen)}
            sx={{ mr: 2, display: { sm: 'none' } }}
            aria-label="open navigation menu"
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
            Data Ingestion Dashboard
          </Typography>
          {user && (
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="body2">{user.email}</Typography>
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  console.log('Logout button clicked');
                  logout.mutate();
                }}
              >
                Logout
              </Button>
            </Box>
          )}
        </Toolbar>
      </AppBar>

      {/* Desktop drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', sm: 'block' },
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
        }}
        open
      >
        {drawer}
      </Drawer>

      {/* Mobile drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', sm: 'none' },
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
        }}
      >
        {drawer}
      </Drawer>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: '64px', // AppBar height
        }}
      >
        <Routes>
          <Route path="/" element={<EmissionsPage />} />
          <Route path="/quality" element={<QualityFlagsPage />} />
          <Route path="/approvals" element={<Placeholder title="Approval Workflow" />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/config" element={<Placeholder title="Configuration" />} />
        </Routes>
      </Box>
    </Box>
  );
}
