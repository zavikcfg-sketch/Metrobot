import SwiftUI

private let boardSize = 10

private struct GridPoint: Hashable {
    let row: Int
    let column: Int
}

private enum BlockColor: String, CaseIterable {
    case blue
    case cyan
    case green
    case orange
    case pink
    case purple
    case red
    case yellow

    var color: Color {
        switch self {
        case .blue:
            return .blue
        case .cyan:
            return .cyan
        case .green:
            return .green
        case .orange:
            return .orange
        case .pink:
            return .pink
        case .purple:
            return .purple
        case .red:
            return .red
        case .yellow:
            return .yellow
        }
    }
}

private struct GamePiece: Identifiable {
    let id = UUID()
    let cells: [GridPoint]
    let color: BlockColor

    var width: Int {
        (cells.map(\.column).max() ?? 0) + 1
    }

    var height: Int {
        (cells.map(\.row).max() ?? 0) + 1
    }
}

@MainActor
private final class GameModel: ObservableObject {
    @Published var board: [[BlockColor?]]
    @Published var pieces: [GamePiece?]
    @Published var selectedSlot: Int?
    @Published var score: Int
    @Published var bestScore: Int
    @Published var isGameOver: Bool

    private let shapes: [[GridPoint]] = [
        [GridPoint(row: 0, column: 0)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 1, column: 0)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 0, column: 2)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 1, column: 0), GridPoint(row: 2, column: 0)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 1, column: 0), GridPoint(row: 1, column: 1)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 1, column: 0), GridPoint(row: 1, column: 1)],
        [GridPoint(row: 0, column: 1), GridPoint(row: 1, column: 0), GridPoint(row: 1, column: 1)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 1, column: 1)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 1, column: 0)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 0, column: 2), GridPoint(row: 1, column: 1)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 1, column: 0), GridPoint(row: 2, column: 0), GridPoint(row: 2, column: 1)],
        [GridPoint(row: 0, column: 1), GridPoint(row: 1, column: 1), GridPoint(row: 2, column: 0), GridPoint(row: 2, column: 1)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 0, column: 2), GridPoint(row: 0, column: 3)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 1, column: 0), GridPoint(row: 2, column: 0), GridPoint(row: 3, column: 0)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 0, column: 2), GridPoint(row: 1, column: 0), GridPoint(row: 1, column: 1), GridPoint(row: 1, column: 2)],
        [GridPoint(row: 0, column: 0), GridPoint(row: 1, column: 0), GridPoint(row: 2, column: 0), GridPoint(row: 0, column: 1), GridPoint(row: 1, column: 1), GridPoint(row: 2, column: 1)]
    ]

    init() {
        board = Self.emptyBoard()
        pieces = []
        selectedSlot = nil
        score = 0
        bestScore = UserDefaults.standard.integer(forKey: "BlockBlastBestScore")
        isGameOver = false
        pieces = Self.makePieces(from: shapes)
    }

    func startNewGame() {
        board = Self.emptyBoard()
        pieces = Self.makePieces(from: shapes)
        selectedSlot = nil
        score = 0
        isGameOver = false
    }

    func select(slot: Int) {
        guard pieces.indices.contains(slot), pieces[slot] != nil, !isGameOver else {
            return
        }

        selectedSlot = selectedSlot == slot ? nil : slot
    }

    func placeSelectedPiece(at row: Int, column: Int) {
        guard
            let selectedSlot,
            pieces.indices.contains(selectedSlot),
            let piece = pieces[selectedSlot],
            canPlace(piece, atRow: row, column: column)
        else {
            return
        }

        for cell in piece.cells {
            board[row + cell.row][column + cell.column] = piece.color
        }

        score += piece.cells.count
        pieces[selectedSlot] = nil
        self.selectedSlot = nil

        clearCompletedLines()

        if pieces.allSatisfy({ $0 == nil }) {
            pieces = Self.makePieces(from: shapes)
        }

        isGameOver = !hasAvailableMove()
        updateBestScore()
    }

    func canPlaceSelectedPiece(at row: Int, column: Int) -> Bool {
        guard
            let selectedSlot,
            pieces.indices.contains(selectedSlot),
            let piece = pieces[selectedSlot]
        else {
            return false
        }

        return canPlace(piece, atRow: row, column: column)
    }

    private func canPlace(_ piece: GamePiece, atRow row: Int, column: Int) -> Bool {
        for cell in piece.cells {
            let targetRow = row + cell.row
            let targetColumn = column + cell.column

            guard
                targetRow >= 0,
                targetRow < boardSize,
                targetColumn >= 0,
                targetColumn < boardSize,
                board[targetRow][targetColumn] == nil
            else {
                return false
            }
        }

        return true
    }

    private func clearCompletedLines() {
        let rowsToClear = Set((0..<boardSize).filter { row in
            board[row].allSatisfy { $0 != nil }
        })

        let columnsToClear = Set((0..<boardSize).filter { column in
            (0..<boardSize).allSatisfy { row in board[row][column] != nil }
        })

        guard !rowsToClear.isEmpty || !columnsToClear.isEmpty else {
            return
        }

        for row in rowsToClear {
            for column in 0..<boardSize {
                board[row][column] = nil
            }
        }

        for column in columnsToClear {
            for row in 0..<boardSize {
                board[row][column] = nil
            }
        }

        let clearedLines = rowsToClear.count + columnsToClear.count
        score += clearedLines * clearedLines * 10
    }

    private func hasAvailableMove() -> Bool {
        for piece in pieces.compactMap({ $0 }) {
            for row in 0..<boardSize {
                for column in 0..<boardSize {
                    if canPlace(piece, atRow: row, column: column) {
                        return true
                    }
                }
            }
        }

        return false
    }

    private func updateBestScore() {
        guard score > bestScore else {
            return
        }

        bestScore = score
        UserDefaults.standard.set(bestScore, forKey: "BlockBlastBestScore")
    }

    private static func emptyBoard() -> [[BlockColor?]] {
        Array(
            repeating: Array(repeating: nil, count: boardSize),
            count: boardSize
        )
    }

    private static func makePieces(from shapes: [[GridPoint]]) -> [GamePiece?] {
        (0..<3).map { _ in
            GamePiece(
                cells: shapes.randomElement() ?? [GridPoint(row: 0, column: 0)],
                color: BlockColor.allCases.randomElement() ?? .blue
            )
        }
    }
}

struct GameView: View {
    @StateObject private var model = GameModel()

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.08, green: 0.10, blue: 0.22), Color(red: 0.16, green: 0.18, blue: 0.34)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 18) {
                header
                board
                pieces
                instructions
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 18)
            .padding(.top, 18)
            .padding(.bottom, 10)
        }
    }

    private var header: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Block Blast")
                        .font(.system(size: 34, weight: .black, design: .rounded))
                        .foregroundStyle(.white)

                    Text("Tap a block, then tap the board")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.65))
                }

                Spacer()

                Button {
                    model.startNewGame()
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundStyle(.white)
                        .frame(width: 44, height: 44)
                        .background(.white.opacity(0.14), in: Circle())
                }
                .accessibilityLabel("New game")
            }

            HStack(spacing: 12) {
                scoreCard(title: "Score", value: model.score)
                scoreCard(title: "Best", value: model.bestScore)
            }
        }
    }

    private func scoreCard(title: String, value: Int) -> some View {
        VStack(spacing: 4) {
            Text(title.uppercased())
                .font(.caption.weight(.bold))
                .foregroundStyle(.white.opacity(0.6))

            Text("\(value)")
                .font(.title2.weight(.black))
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var board: some View {
        GeometryReader { proxy in
            let side = min(proxy.size.width, proxy.size.height)
            let spacing: CGFloat = 4
            let cellSide = (side - spacing * CGFloat(boardSize - 1)) / CGFloat(boardSize)

            VStack(spacing: spacing) {
                ForEach(0..<boardSize, id: \.self) { row in
                    HStack(spacing: spacing) {
                        ForEach(0..<boardSize, id: \.self) { column in
                            cellView(row: row, column: column, side: cellSide)
                        }
                    }
                }
            }
            .frame(width: side, height: side)
            .padding(10)
            .background(.black.opacity(0.22), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay {
                if model.isGameOver {
                    gameOverOverlay
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .aspectRatio(1, contentMode: .fit)
    }

    private func cellView(row: Int, column: Int, side: CGFloat) -> some View {
        let color = model.board[row][column]?.color
        let canPlace = model.canPlaceSelectedPiece(at: row, column: column)

        return RoundedRectangle(cornerRadius: 7, style: .continuous)
            .fill(color ?? (canPlace ? Color.white.opacity(0.25) : Color.white.opacity(0.08)))
            .overlay {
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .stroke(.white.opacity(color == nil ? 0.07 : 0.2), lineWidth: 1)
            }
            .frame(width: side, height: side)
            .shadow(color: (color ?? .clear).opacity(0.32), radius: 4, y: 2)
            .contentShape(Rectangle())
            .onTapGesture {
                model.placeSelectedPiece(at: row, column: column)
            }
    }

    private var pieces: some View {
        HStack(spacing: 12) {
            ForEach(model.pieces.indices, id: \.self) { index in
                pieceSlot(index: index)
            }
        }
    }

    private func pieceSlot(index: Int) -> some View {
        let isSelected = model.selectedSlot == index

        return Button {
            model.select(slot: index)
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(isSelected ? Color.white.opacity(0.24) : Color.white.opacity(0.10))
                    .overlay {
                        RoundedRectangle(cornerRadius: 20, style: .continuous)
                            .stroke(isSelected ? .white : .white.opacity(0.12), lineWidth: isSelected ? 2 : 1)
                    }

                if let piece = model.pieces[index] {
                    PiecePreview(piece: piece)
                        .padding(12)
                } else {
                    Text("Done")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.white.opacity(0.45))
                }
            }
            .frame(height: 108)
        }
        .buttonStyle(.plain)
    }

    private var instructions: some View {
        VStack(spacing: 8) {
            Text("Fill a full row or column to clear it.")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.white.opacity(0.7))

            if model.isGameOver {
                Button("New Game") {
                    model.startNewGame()
                }
                .font(.headline.weight(.bold))
                .foregroundStyle(.white)
                .padding(.horizontal, 22)
                .padding(.vertical, 12)
                .background(Color.blue, in: Capsule())
            }
        }
    }

    private var gameOverOverlay: some View {
        VStack(spacing: 12) {
            Text("Game Over")
                .font(.largeTitle.weight(.black))

            Text("Score: \(model.score)")
                .font(.headline.weight(.bold))

            Button("Play Again") {
                model.startNewGame()
            }
            .font(.headline.weight(.bold))
            .padding(.horizontal, 22)
            .padding(.vertical, 12)
            .background(Color.blue, in: Capsule())
        }
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.black.opacity(0.72), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

private struct PiecePreview: View {
    let piece: GamePiece

    var body: some View {
        GeometryReader { proxy in
            let previewSize = min(proxy.size.width, proxy.size.height)
            let side = min(previewSize / CGFloat(max(piece.width, piece.height)), 24)
            let totalWidth = CGFloat(piece.width) * side
            let totalHeight = CGFloat(piece.height) * side

            ZStack(alignment: .topLeading) {
                ForEach(piece.cells, id: \.self) { cell in
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .fill(piece.color.color)
                        .frame(width: side - 3, height: side - 3)
                        .offset(x: CGFloat(cell.column) * side, y: CGFloat(cell.row) * side)
                        .shadow(color: piece.color.color.opacity(0.35), radius: 4, y: 2)
                }
            }
            .frame(width: totalWidth, height: totalHeight)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

#Preview {
    GameView()
}
