import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { Layout } from "./components/Layout";
import Overview from "./pages/Overview";
import Forecasting from "./pages/Forecasting";
import Planning from "./pages/Planning";
import Scheduling from "./pages/Scheduling";
import Machines from "./pages/Machines";
import Simulation from "./pages/Simulation";
import Reports from "./pages/Reports";

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/forecasting" element={<Forecasting />} />
            <Route path="/planning" element={<Planning />} />
            <Route path="/scheduling" element={<Scheduling />} />
            <Route path="/machines" element={<Machines />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/reports" element={<Reports />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  );
}
