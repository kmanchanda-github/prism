import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AnalysisPage } from "./pages/Analysis";
import { SubmitPage } from "./pages/Submit";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<SubmitPage />} />
          <Route path="/analysis/:id" element={<AnalysisPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
