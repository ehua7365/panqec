import itertools
from typing import Tuple
import numpy as np
from ..generic._indexed_code import IndexedCode
from ._rhombic_pauli import RhombicPauli


class RhombicCode(IndexedCode):

    pauli_class = RhombicPauli

    # StabilizerCode interface methods.

    @property
    def n_k_d(self) -> Tuple[int, int, int]:
        return (3 * np.product(self.size), 3, min(self.size))

    @property
    def label(self) -> str:
        return 'Rhombic {}x{}x{}'.format(*self.size)

    @property
    def logical_xs(self) -> np.ndarray:
        """The 3 logical X operators."""

        if self._logical_xs.size == 0:
            Lx, Ly, Lz = self.size
            logicals = []

            # Sheet of X operators normal to the z direction
            logical = self.pauli_class(self)
            for x in range(2*Lx):
                for y in range(2*Ly):
                    if (x + y) % 2 == 1:
                        logical.site('X', (x, y, 0))
            logicals.append(logical.to_bsf())

            # Sheet of X operators normal to the y direction
            logical = self.pauli_class(self)
            for x in range(2*Lx):
                for z in range(2*Lz):
                    if (x + z) % 2 == 1:
                        logical.site('X', (x, 0, z))
            logicals.append(logical.to_bsf())

            # Sheet of X operators normal to the x direction
            logical = self.pauli_class(self)
            for y in range(2*Ly):
                for z in range(2*Lz):
                    if (y + z) % 2 == 1:
                        logical.site('X', (0, y, z))
            logicals.append(logical.to_bsf())

            self._logical_xs = np.array(logicals, dtype=np.uint)

        return self._logical_xs

    @property
    def logical_zs(self) -> np.ndarray:
        """Get the 3 logical Z operators."""
        if self._logical_zs.size == 0:
            Lx, Ly, Lz = self.size
            logicals = []

            # Line of parallel Z operators along the x direction
            logical = self.pauli_class(self)
            for x in range(0, 2*Lx, 2):
                logical.site('Z', (x, 1, 0))
            logicals.append(logical.to_bsf())

            # Line of parallel Z operators along the y direction
            logical = self.pauli_class(self)
            for y in range(0, 2*Ly, 2):
                logical.site('Z', (1, y, 0))
            logicals.append(logical.to_bsf())

            # Line of parallel Z operators along the z direction
            logical = self.pauli_class(self)
            for z in range(0, 2*Lz, 2):
                logical.site('Z', (0, 1, z))
            logicals.append(logical.to_bsf())

            self._logical_zs = np.array(logicals, dtype=np.uint)

        return self._logical_zs

    def axis(self, location):
        x, y, z = location

        if (z % 2 == 0) and (x % 2 == 1) and (y % 2 == 0):
            axis = self.X_AXIS
        elif (z % 2 == 0) and (x % 2 == 0) and (y % 2 == 1):
            axis = self.Y_AXIS
        elif (z % 2 == 1) and (x % 2 == 0) and (y % 2 == 0):
            axis = self.Z_AXIS
        else:
            raise ValueError(f'Location {location} does not correspond to a qubit')

        return axis

    def _create_qubit_indices(self):
        coordinates = []
        Lx, Ly, Lz = self.size

        # Qubits along e_x
        for x in range(1, 2*Lx, 2):
            for y in range(0, 2*Ly, 2):
                for z in range(0, 2*Lz, 2):
                    coordinates.append((x, y, z))

        # Qubits along e_y
        for x in range(0, 2*Lx, 2):
            for y in range(1, 2*Ly, 2):
                for z in range(0, 2*Lz, 2):
                    coordinates.append((x, y, z))

        # Qubits along e_z
        for x in range(0, 2*Lx, 2):
            for y in range(0, 2*Ly, 2):
                for z in range(1, 2*Lz, 2):
                    coordinates.append((x, y, z))

        coord_to_index = {coord: i for i, coord in enumerate(coordinates)}

        return coord_to_index

    def _create_vertex_indices(self):
        """ Vertex = triangle stabilizer"""
        coordinates = []
        Lx, Ly, Lz = self.size

        for x in range(0, 2*Lx, 2):
            for y in range(0, 2*Ly, 2):
                for z in range(0, 2*Lz, 2):
                    for axis in range(4):
                        coordinates.append((axis, x, y, z))

        coord_to_index = {coord: i for i, coord in enumerate(coordinates)}

        return coord_to_index

    def _create_face_indices(self):
        """ Face = cube stabilizer"""
        Lx, Ly, Lz = self.size

        ranges = [range(1, 2*Lx, 2), range(1, 2*Ly, 2), range(1, 2*Lz, 2)]
        coordinates = []
        print(list(itertools.product(*ranges)))
        for x, y, z in itertools.product(*ranges):
            if (x + y + z) % 4 == 1:
                coordinates.append((x, y, z))

        coord_to_index = {coord: i for i, coord in enumerate(coordinates)}

        return coord_to_index
