package com.employee.system.service;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class AttendanceSummary {
    private Long employeeId;
    private long totalDays;
    private long presentDays;
    private long absentDays;
    private long lateDays;
    private long halfDays;
    private long leaveDays;
}
