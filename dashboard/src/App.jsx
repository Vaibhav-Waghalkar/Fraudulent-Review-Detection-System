import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import ReviewsPage from "./pages/ReviewsPage.jsx";
import DriftPage from "./pages/DriftPage.jsx";
import ReviewDetailPage from "./pages/ReviewDetailPage.jsx";
import ModelPage from "./pages/ModelPage.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/reviews/:id" element={<ReviewDetailPage />} />
        <Route path="/drift" element={<DriftPage />} />
        <Route path="/model" element={<ModelPage />} />
      </Routes>
    </Layout>
  );
}
