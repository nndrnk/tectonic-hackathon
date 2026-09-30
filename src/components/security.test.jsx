import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import conflictMock from "../mock_response.json";
import AnswerCard from "./AnswerCard.jsx";
import ClaimTree from "./ClaimTree.jsx";
import DocumentDetail from "./DocumentDetail.jsx";

describe("rendu sûr et explication des résultats", () => {
  it("affiche un titre malveillant comme texte sans créer d'élément image", () => {
    const unsafeTitle = "<img src=x onerror=alert(1)>";
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const source = {
      ...conflictMock.branches[0].sources[0],
      title: unsafeTitle,
    };

    const { container } = render(<DocumentDetail onVote={vi.fn()} source={source} />);

    expect(screen.getByText(unsafeTitle)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it("explique pourquoi il y a conflit et ce qui manque", () => {
    render(<AnswerCard result={conflictMock} />);

    expect(screen.getByText(/Pourquoi:/i)).toBeInTheDocument();
    expect(screen.getByText(/Ce qui manque:/i)).toBeInTheDocument();
  });

  it("marque une copie comme comptée une seule fois", () => {
    const branch = conflictMock.branches[0];
    render(<ClaimTree branches={[branch]} onSelectSource={vi.fn()} query="Question de test" />);

    expect(screen.getAllByText(/copie \(comptée 1 fois\)/i).length).toBe(3);
  });
});
