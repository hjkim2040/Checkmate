package com.checkmate.domain.contract.repository;

import com.checkmate.domain.contract.entity.Contract;
import com.checkmate.domain.contract.entity.EditStatus;
import com.checkmate.domain.contract.entity.SignatureStatus;
import com.checkmate.domain.contractcategory.entity.ContractCategory;
import com.checkmate.domain.user.entity.User;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ContractRepository extends JpaRepository<Contract, Integer> {
    /**
     * 사용자별 모든 계약서 조회
     *
     * @param user 사용자 엔티티
     * @return 해당 사용자의 모든 계약서 목록
     */
    @EntityGraph(attributePaths = "category")
    List<Contract> findAllByUser(User user);

    /**
     * 사용자, 카테고리, 편집 상태로 계약서 조회
     * 특정 사용자의 특정 카테고리와 편집 상태에 해당하는 계약서 조회
     *
     * @param user 사용자 엔티티
     * @param category 계약서 카테고리 엔티티
     * @param editStatus 편집 상태 (EDITING, COMPLETED 등)
     * @return 조건에 맞는 계약서
     */
    Optional<Contract> findByUserAndCategoryAndEditStatus(User user, ContractCategory category, EditStatus editStatus);

    /**
     * 전자서명 요청 ID로 계약서 조회
     *
     * @param signatureRequestId 전자서명 요청 ID
     * @return 해당 전자서명 요청 ID를 가진 계약서
     */
    Optional<Contract> findBySignatureRequestId(String signatureRequestId);

    /**
     * 계약서 ID와 서명 상태로 계약서 존재 여부 확인
     *
     * @param contractId 계약서 ID
     * @param signatureStatus 서명 상태 (PENDING, COMPLETED 등)
     * @return 해당 조건의 계약서 존재 여부
     */
    boolean existsByIdAndSignatureStatus(Integer contractId, SignatureStatus signatureStatus);
}
