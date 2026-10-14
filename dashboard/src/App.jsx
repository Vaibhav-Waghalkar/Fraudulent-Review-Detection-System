import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ReviewsPage from "./pages/ReviewsPage.jsx";
import DriftPage from "./pages/DriftPage.jsx";
import ReviewDetailPage from "./pages/ReviewDetailPage.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/reviews" replace />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/reviews/:id" element={<ReviewDetailPage />} />
        <Route path="/drift" element={<DriftPage />} />
      </Routes>
    </Layout>
  );
}
