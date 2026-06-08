/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import EnrollmentUpload from './pages/EnrollmentUpload';
import CoursesQuery from './pages/CoursesQuery';
import GraduationCheck from './pages/GraduationCheck';
import CourseRecommendation from './pages/CourseRecommendation';
import SidebarLayout from './layouts/SidebarLayout';

function isAuthenticated() {
  return Boolean(localStorage.getItem('token') && localStorage.getItem('isLoggedIn'));
}

function ProtectedPage({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  return <SidebarLayout>{children}</SidebarLayout>;
}

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Auth Page */}
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/login" replace />} />

        {/* Dashboard SaaS Views wrapped in persistent SidebarLayout */}
        <Route 
          path="/dashboard" 
          element={
            <ProtectedPage>
              <Dashboard />
            </ProtectedPage>
          } 
        />
        <Route 
          path="/upload" 
          element={
            <ProtectedPage>
              <EnrollmentUpload />
            </ProtectedPage>
          } 
        />
        <Route 
          path="/courses" 
          element={
            <ProtectedPage>
              <CoursesQuery />
            </ProtectedPage>
          } 
        />
        <Route 
          path="/check" 
          element={
            <ProtectedPage>
              <GraduationCheck />
            </ProtectedPage>
          } 
        />
        <Route 
          path="/recommendations" 
          element={
            <ProtectedPage>
              <CourseRecommendation />
            </ProtectedPage>
          } 
        />

        {/* Fallback Catch and redirect */}
        <Route 
          path="*" 
          element={<Navigate to="/login" replace />} 
        />
      </Routes>
    </Router>
  );
}
