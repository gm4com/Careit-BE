SELECT TOP 1000
       a.*
  FROM (
        SELECT
              ia.UID                                      AS h_uid
            , ib.UserPass                                 AS password        
            , ia.LastLoginDate                            AS last_login
            , ia.RegDate                                  AS created_datetime
            , LEFT(ib.UserName,20)                        AS username
            , CASE WHEN ia.T_Birth = '' THEN NULL 
                                        ELSE REPLACE(ia.T_Birth,' ', '') 
                                        END               AS date_of_birth
            , CASE WHEN ia.T_SEX IS NULL
                    AND ib.Sex = 'W'     THEN 'Y'
                   WHEN ia.T_SEX IS NULL
                    AND ib.Sex = 'M'     THEN 'N'
                   WHEN ia.T_SEX = ''
                    AND ib.Sex = 'W'     THEN 'Y'
                   WHEN ia.T_SEX = ''
                    AND ib.Sex = 'M'     THEN 'N'
                   WHEN ia.T_SEX = ''    THEN ib.Sex
                   WHEN ia.T_SEX = '남성' THEN 'N'
                   WHEN ia.T_SEX = '여성' THEN 'Y'
                                         ELSE ''
                                         END
                                                          AS gender
            , ia.OutDate                                  AS withdrew_datetime
            , ia.IsBlock                                  AS _is_service_blocked
            , CASE WHEN ib.UserID   = ''
                     OR ib.UserID   IS NULL THEN CONCAT(ia.AM_UserID,ia.uid,'@')
                                            ELSE CONCAT(ib.UserID,ia.uid,'@')
                                             END
                                                          AS email

            , CASE WHEN ia.ErrandTel IS NULL
                    AND ia.ErrandTel = ''   THEN LEFT(ia.UserHP,11)
                                            ELSE LEFT(ia.ErrandTel,11) END 
                                                          AS number

            , ia.BlockDate                                AS start_datetime
            , CONVERT(datetime, ia.BlockEndDate)          AS end_datetime
           

            , CASE WHEN ia.IsBlock      =  'N'
                    AND ia.IsOut        =  'N'
                    AND ia.AM_UserID    <> ''
                    AND ib.IsRealAuthor =  'Y'  THEN '20' /* 20 정식헬퍼 */
                   WHEN ia.IsBlock      =  'N'
                    AND ia.IsOut        =  'N'
                    AND ib.IsRealAuthor =  'N'  THEN '30' /* 30 임시헬퍼 */
                   WHEN ia.IsBlock      =  'Y'  THEN '40' /* 40 블락헬퍼 */
                   WHEN ia.isOut        =  'Y'  THEN '80' /* 80 탈퇴헬퍼 */
                                                ELSE '90' /* 90 기타    */
                                                 END
                                                          AS helper_grade           
           
           
            , CASE 
                   WHEN ia.S_H IS NULL THEN '00:00'
                   WHEN ia.S_H = ''    THEN '00:00'
                  --  WHEN ia.S_H IN ('00')
                   ELSE CONCAT(CONVERT(varchar(2),ia.S_H),':00') END   AS push_not_allowed_from
            , CASE 
                   WHEN ia.E_H IS NULL THEN '00:00'
                   WHEN ia.E_H = ''    THEN '00:00'
                   ELSE CONCAT(CONVERT(varchar(2),ia.E_H),':00') END   AS push_not_allowed_to

            , ia.T_INTRODUCE                              AS introduction
            , ia.Bank                                     AS bank_code
            , ia.BankNum                                  AS bank_number
            
            , LEFT(ia.BankUser,20)                        AS bank_name

        FROM na52791588.dbo.M_AM_HELPER ia /* 헬퍼기본 */
        LEFT JOIN
             na52791588.dbo.AM_MEMBER   ib /* 멤버기본 */
          ON ia.AM_UserID = ib.UserID

        --  AND ia.BlockDate IS NOT NULL
        
     ) a
 WHERE 1=1
   AND a.password IS NOT NULL
 ORDER BY created_datetime